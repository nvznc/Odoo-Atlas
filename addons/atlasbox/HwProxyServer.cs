using System;
using System.Collections.Generic;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;

namespace JPosBox
{
    /// <summary>
    /// Servidor HTTP minimo (TcpListener) que implementa los endpoints hw_proxy
    /// que usa Odoo POS. No requiere permisos de administrador ni reservas URL.
    /// </summary>
    public class HwProxyServer
    {
        private TcpListener _listener;
        private Thread _thread;
        private volatile bool _running;

        public string Name { get; private set; }
        public int Port { get; private set; }
        public string PrinterName { get; set; }
        public float FontSize { get; set; }
        public int PaperWidthMm { get; set; }
        public string PdfOutputDir { get; set; }

        public bool IsRunning
        {
            get { return _running; }
        }

        public HwProxyServer(string name, int port, string printerName, float fontSize,
            int paperWidthMm, string pdfOutputDir)
        {
            Name = name;
            Port = port;
            PrinterName = printerName;
            FontSize = fontSize;
            PaperWidthMm = paperWidthMm;
            PdfOutputDir = pdfOutputDir;
        }

        // ------------------------------------------------------------------
        // Ciclo de vida
        // ------------------------------------------------------------------

        public bool Start(out string error)
        {
            error = null;

            if (_running)
            {
                return true;
            }

            TcpListener listener = null;

            try
            {
                listener = new TcpListener(IPAddress.Any, Port);
                listener.Start();
            }
            catch (Exception ex)
            {
                if (listener != null)
                {
                    try { listener.Stop(); }
                    catch { }
                }

                error = ex.Message;
                Log.Write("{0}: no se pudo abrir el puerto {1}: {2}", Name, Port, ex.Message);
                return false;
            }

            _listener = listener;
            _running = true;

            _thread = new Thread(AcceptLoop);
            _thread.IsBackground = true;
            _thread.Name = Name;
            _thread.Start();

            Log.Write("{0}: escuchando en el puerto {1} (impresora: {2})",
                Name, Port, DescribePrinter());

            return true;
        }

        public void Stop()
        {
            if (!_running)
            {
                return;
            }

            _running = false;

            try
            {
                if (_listener != null)
                {
                    _listener.Stop();
                }
            }
            catch
            {
            }

            _listener = null;
            _thread = null;

            Log.Write("{0}: detenido (puerto {1}).", Name, Port);
        }

        private string DescribePrinter()
        {
            if (string.IsNullOrEmpty(PrinterName) || PrinterName == "nada")
            {
                return "sin configurar";
            }
            return PrinterName;
        }

        // ------------------------------------------------------------------
        // Bucle de aceptacion y peticiones
        // ------------------------------------------------------------------

        private void AcceptLoop()
        {
            while (_running)
            {
                TcpClient client = null;

                try
                {
                    client = _listener.AcceptTcpClient();
                }
                catch
                {
                    if (!_running)
                    {
                        break;
                    }
                    continue;
                }

                ThreadPool.QueueUserWorkItem(HandleClient, client);
            }
        }

        private void HandleClient(object state)
        {
            TcpClient client = (TcpClient)state;
            string remote = "";

            try
            {
                remote = client.Client.RemoteEndPoint.ToString();
            }
            catch
            {
            }

            try
            {
                client.ReceiveTimeout = 15000;
                client.SendTimeout = 60000;

                NetworkStream ns = client.GetStream();
                BufferedStream input = new BufferedStream(ns, 8192);

                string headerText = ReadHeaders(input);
                if (string.IsNullOrEmpty(headerText))
                {
                    return;
                }

                string[] lines = headerText.Split(new string[] { "\r\n" }, StringSplitOptions.None);
                string[] requestLine = lines[0].Split(' ');

                if (requestLine.Length < 2)
                {
                    WriteResponse(ns, 400, "Bad Request", "text/plain", "Bad Request");
                    return;
                }

                string method = requestLine[0].ToUpperInvariant();
                string target = requestLine[1];
                string path = target;
                int q = target.IndexOf('?');
                if (q >= 0)
                {
                    path = target.Substring(0, q);
                }

                Dictionary<string, string> headers =
                    new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

                for (int i = 1; i < lines.Length; i++)
                {
                    int colon = lines[i].IndexOf(':');
                    if (colon <= 0)
                    {
                        continue;
                    }

                    string key = lines[i].Substring(0, colon).Trim();
                    string value = lines[i].Substring(colon + 1).Trim();

                    if (!headers.ContainsKey(key))
                    {
                        headers[key] = value;
                    }
                }

                string body = ReadBody(input, headers);
                Log.Write("{0}: {1} {2}", Name, method, path);

                if (method == "OPTIONS")
                {
                    WriteResponse(ns, 200, "OK", "text/plain", "");
                    return;
                }

                string route = NormalizeRoute(path);
                if (route.Length == 0)
                {
                    route = "/";
                }

                if (route.Equals("/hw_proxy/hello", StringComparison.OrdinalIgnoreCase))
                {
                    WriteResponse(ns, 200, "OK", "text/plain", "ping");
                }
                else if (route.Equals("/hw_proxy/handshake", StringComparison.OrdinalIgnoreCase))
                {
                    WriteResponse(ns, 200, "OK", "application/json", BuildAck(body));
                }
                else if (route.Equals("/hw_proxy/status_json", StringComparison.OrdinalIgnoreCase))
                {
                    WriteResponse(ns, 200, "OK", "application/json", BuildStatus(body));
                }
                else if (route.Equals("/hw_proxy/print_xml_receipt", StringComparison.OrdinalIgnoreCase))
                {
                    HandlePrint(body);
                    WriteResponse(ns, 200, "OK", "application/json", BuildAck(body));
                }
                else if (route.Equals("/hw_proxy/default_printer_action", StringComparison.OrdinalIgnoreCase))
                {
                    WriteResponse(ns, 200, "OK", "application/json", HandlePrinterAction(body));
                }
                else if (route == "/")
                {
                    WriteResponse(ns, 200, "OK", "text/plain", "jPosBox listo");
                }
                else
                {
                    WriteResponse(ns, 404, "Not Found", "text/plain", "Not Found");
                }
            }
            catch (Exception ex)
            {
                Log.Write("{0}: error procesando la peticion de {1}: {2}", Name, remote, ex.Message);
            }
            finally
            {
                try { client.Close(); }
                catch { }
            }
        }

        // ------------------------------------------------------------------
        // Respuestas JSON-RPC
        // ------------------------------------------------------------------

        private static string BuildAck(string body)
        {
            return "{\"jsonrpc\": \"2.0\", \"id\": " + ReceiptParser.ExtractJsonId(body) + ", \"result\": true}";
        }

        private static string BuildError(string body, string message)
        {
            return "{\"jsonrpc\": \"2.0\", \"id\": " + ReceiptParser.ExtractJsonId(body)
                + ", \"error\": {\"code\": -32000, \"message\": \""
                + ReceiptParser.EscapeJson(message) + "\"}}";
        }

        private static string NormalizeRoute(string path)
        {
            string route = path.TrimEnd('/');

            // Permite URLs con prefijo, por ejemplo http://ip:6060/cocina/hw_proxy/hello
            int index = route.IndexOf("/hw_proxy/", StringComparison.OrdinalIgnoreCase);
            if (index > 0)
            {
                route = route.Substring(index);
            }

            return route;
        }

        private string BuildStatus(string body)
        {
            string id = ReceiptParser.ExtractJsonId(body);
            bool configured = !(string.IsNullOrEmpty(PrinterName)
                || PrinterName.Equals("nada", StringComparison.OrdinalIgnoreCase));
            string message = configured
                ? "Conectado a " + PrinterName
                : "Sin impresora configurada";

            return "{\"jsonrpc\": \"2.0\", \"id\": " + id + ", \"result\": {"
                + "\"scale\": {\"status\": \"disconnected\", \"messages\": [\"No se encontro ningun dispositivo RS-232\"]}, "
                + "\"scanner\": {\"status\": \"error\", \"messages\": [\"Escaner no configurado\"]}, "
                + "\"escpos\": {\"status\": \"connected\", \"messages\": [\""
                + ReceiptParser.EscapeJson(message) + "\"]}}}";
        }

        private void HandlePrint(string body)
        {
            try
            {
                string xml = ReceiptParser.ExtractReceiptXml(body);

                if (xml == null)
                {
                    Log.Write("{0}: la peticion no contiene ningun ticket.", Name);
                    return;
                }

                ReceiptDocument receipt = ReceiptParser.ParseXml(xml);
                Log.Write("{0}: ticket '{1}' con {2} elementos.",
                    Name, receipt.DocumentType, receipt.Elements.Count);

                string pdfPath = PrintOutput.Resolve(PdfOutputDir, PrinterName, "ticket");

                if (pdfPath == null && PrintOutput.IsPdfPrinter(PrinterName))
                {
                    Log.Write("{0}: la impresora '{1}' es PDF y PdfOutputDir esta vacio. " +
                              "Configura la carpeta de salida PDF.", Name, PrinterName);
                    return;
                }

                using (ReceiptPrinter printer = new ReceiptPrinter(receipt.Elements, FontSize, PaperWidthMm))
                {
                    printer.Print(PrinterName, pdfPath);
                }
            }
            catch (Exception ex)
            {
                Log.Write("{0}: error al imprimir el ticket: {1}", Name, ex.Message);
            }
        }

        /// <summary>
        /// Endpoint que usa el modulo jIotBox de Odoo para las comandas:
        /// params.data.action = "print_receipt", params.data.receipt = imagen base64.
        /// </summary>
        private string HandlePrinterAction(string body)
        {
            string action = ReceiptParser.ExtractJsonString(body, "action");

            if (string.IsNullOrEmpty(action))
            {
                return BuildError(body, "La peticion no incluye el campo 'action'.");
            }

            if (!action.Equals("print_receipt", StringComparison.OrdinalIgnoreCase))
            {
                return BuildError(body, "Accion no soportada: " + action);
            }

            string receiptBase64 = ReceiptParser.ExtractJsonString(body, "receipt");

            if (string.IsNullOrEmpty(receiptBase64))
            {
                return BuildError(body, "La comanda no incluye la imagen 'receipt'.");
            }

            string error;

            if (!PrintBase64Image(receiptBase64, out error))
            {
                return BuildError(body, error);
            }

            return BuildAck(body);
        }

        private bool PrintBase64Image(string receiptBase64, out string error)
        {
            error = null;

            if (string.IsNullOrEmpty(PrinterName)
                || PrinterName.Equals("nada", StringComparison.OrdinalIgnoreCase))
            {
                error = "No hay impresora configurada en jPosBox.";
                return false;
            }

            // Admite tanto base64 puro como "data:image/png;base64,....".
            int comma = receiptBase64.IndexOf("base64,", StringComparison.OrdinalIgnoreCase);
            if (comma >= 0)
            {
                receiptBase64 = receiptBase64.Substring(comma + 7);
            }

            byte[] bytes;

            try
            {
                bytes = Convert.FromBase64String(receiptBase64.Trim());
            }
            catch (FormatException)
            {
                error = "La imagen de la comanda no es base64 valido.";
                return false;
            }

            try
            {
                using (MemoryStream stream = new MemoryStream(bytes))
                using (Image image = Image.FromStream(stream))
                {
                    string pdfPath = PrintOutput.Resolve(PdfOutputDir, PrinterName, "comanda");

                    if (pdfPath == null && PrintOutput.IsPdfPrinter(PrinterName))
                    {
                        error = "La impresora es PDF y PdfOutputDir esta vacio. " +
                                "Configura la carpeta de salida PDF en jPosBox.";
                        return false;
                    }

                    ImagePrinter printer = new ImagePrinter(image, PaperWidthMm);

                    if (!printer.Print(PrinterName, pdfPath))
                    {
                        error = "No se pudo imprimir en '" + PrinterName + "'. Revisa el log de jPosBox.";
                        return false;
                    }
                }

                return true;
            }
            catch (Exception ex)
            {
                error = "No se pudo interpretar la imagen de la comanda: " + ex.Message;
                return false;
            }
        }

        // ------------------------------------------------------------------
        // Lectura HTTP
        // ------------------------------------------------------------------

        private static string ReadHeaders(Stream stream)
        {
            MemoryStream buffer = new MemoryStream();
            int last4 = 0;
            int b;

            while ((b = stream.ReadByte()) != -1)
            {
                buffer.WriteByte((byte)b);
                last4 = (last4 << 8) | (b & 0xFF);

                if (last4 == 0x0D0A0D0A)
                {
                    break;
                }

                if (buffer.Length > 65536)
                {
                    return null;
                }
            }

            if (buffer.Length == 0)
            {
                return null;
            }

            return Encoding.UTF8.GetString(buffer.ToArray());
        }

        private static string ReadBody(Stream stream, Dictionary<string, string> headers)
        {
            string transferEncoding;
            if (headers.TryGetValue("Transfer-Encoding", out transferEncoding)
                && transferEncoding.IndexOf("chunked", StringComparison.OrdinalIgnoreCase) >= 0)
            {
                return Encoding.UTF8.GetString(ReadChunked(stream));
            }

            int contentLength = 0;
            string rawLength;

            if (headers.TryGetValue("Content-Length", out rawLength))
            {
                int.TryParse(rawLength, NumberStyles.Integer, CultureInfo.InvariantCulture, out contentLength);
            }

            if (contentLength <= 0)
            {
                return "";
            }

            if (contentLength > 32 * 1024 * 1024)
            {
                throw new IOException("Cuerpo de peticion demasiado grande");
            }

            byte[] bytes = ReadExact(stream, contentLength);
            return Encoding.UTF8.GetString(bytes);
        }

        private static byte[] ReadChunked(Stream stream)
        {
            MemoryStream result = new MemoryStream();

            while (true)
            {
                string line = ReadLine(stream);
                if (line == null)
                {
                    break;
                }

                int semi = line.IndexOf(';');
                if (semi >= 0)
                {
                    line = line.Substring(0, semi);
                }

                int size;
                if (!int.TryParse(line.Trim(), NumberStyles.HexNumber, CultureInfo.InvariantCulture, out size))
                {
                    break;
                }

                if (size == 0)
                {
                    ReadLine(stream);
                    break;
                }

                byte[] chunk = ReadExact(stream, size);
                result.Write(chunk, 0, chunk.Length);
                ReadLine(stream);
            }

            return result.ToArray();
        }

        private static string ReadLine(Stream stream)
        {
            StringBuilder sb = new StringBuilder();
            int b;

            while ((b = stream.ReadByte()) != -1)
            {
                if (b == '\n')
                {
                    break;
                }
                if (b != '\r')
                {
                    sb.Append((char)b);
                }
            }

            if (b == -1 && sb.Length == 0)
            {
                return null;
            }

            return sb.ToString();
        }

        private static byte[] ReadExact(Stream stream, int count)
        {
            byte[] buffer = new byte[count];
            int offset = 0;

            while (offset < count)
            {
                int read = stream.Read(buffer, offset, count - offset);
                if (read <= 0)
                {
                    throw new IOException("Fin inesperado del cuerpo de la peticion");
                }
                offset += read;
            }

            return buffer;
        }

        private static void WriteResponse(NetworkStream ns, int code, string reason, string contentType, string body)
        {
            byte[] bytes = Encoding.UTF8.GetBytes(body ?? "");

            StringBuilder head = new StringBuilder();
            head.Append("HTTP/1.1 ").Append(code).Append(' ').Append(reason).Append("\r\n");
            head.Append("Content-Type: ").Append(contentType).Append("; charset=utf-8\r\n");
            head.Append("Content-Length: ").Append(bytes.Length).Append("\r\n");
            head.Append("Access-Control-Allow-Origin: *\r\n");
            head.Append("Access-Control-Allow-Methods: POST, GET, OPTIONS\r\n");
            head.Append("Access-Control-Allow-Headers: Origin, X-Requested-With, Content-Type, Accept, X-Debug-Mode\r\n");
            head.Append("Access-Control-Allow-Private-Network: true\r\n");
            head.Append("Cache-Control: no-store\r\n");
            head.Append("Connection: close\r\n\r\n");

            byte[] headBytes = Encoding.ASCII.GetBytes(head.ToString());
            ns.Write(headBytes, 0, headBytes.Length);

            if (bytes.Length > 0)
            {
                ns.Write(bytes, 0, bytes.Length);
            }

            ns.Flush();
        }
    }
}
