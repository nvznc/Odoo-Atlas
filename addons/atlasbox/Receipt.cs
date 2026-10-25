using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using System.Xml;

namespace JPosBox
{
    public enum ReceiptElementKind
    {
        Left,
        Center,
        Row,
        Divider,
        Spacer
    }

    /// <summary>Un trozo de ticket ya interpretado, listo para dibujar.</summary>
    public class ReceiptElement
    {
        public ReceiptElementKind Kind;
        public string Text = "";
        public string Right = "";
        public bool Bold;

        public static ReceiptElement LeftAligned(string text)
        {
            ReceiptElement e = new ReceiptElement();
            e.Kind = ReceiptElementKind.Left;
            e.Text = text ?? "";
            return e;
        }

        public static ReceiptElement LeftAligned(string text, bool bold)
        {
            ReceiptElement e = LeftAligned(text);
            e.Bold = bold;
            return e;
        }

        public static ReceiptElement Centered(string text)
        {
            ReceiptElement e = new ReceiptElement();
            e.Kind = ReceiptElementKind.Center;
            e.Text = text ?? "";
            return e;
        }

        public static ReceiptElement Row(string left, string right, bool bold)
        {
            ReceiptElement e = new ReceiptElement();
            e.Kind = ReceiptElementKind.Row;
            e.Text = left ?? "";
            e.Right = right ?? "";
            e.Bold = bold;
            return e;
        }

        public static ReceiptElement Divider()
        {
            ReceiptElement e = new ReceiptElement();
            e.Kind = ReceiptElementKind.Divider;
            return e;
        }

        public static ReceiptElement Spacer()
        {
            ReceiptElement e = new ReceiptElement();
            e.Kind = ReceiptElementKind.Spacer;
            return e;
        }
    }

    public class ReceiptDocument
    {
        public readonly List<ReceiptElement> Elements = new List<ReceiptElement>();
        public string DocumentType = "ticket";
        public string RawXml = "";
        public bool Parsed;
    }

    /// <summary>
    /// Interpreta el ticket XML que envia Odoo POS a /hw_proxy/print_xml_receipt.
    /// Se mantiene la misma logica XPath que la version Java.
    /// </summary>
    public static class ReceiptParser
    {
        // ------------------------------------------------------------------
        // Extraccion del cuerpo JSON-RPC
        // ------------------------------------------------------------------

        public static string ExtractJsonId(string body)
        {
            if (string.IsNullOrEmpty(body))
            {
                return "null";
            }

            Match m = Regex.Match(
                body,
                "\"id\"\\s*:\\s*(\"(?:[^\"\\\\]|\\\\.)*\"|-?[0-9]+(?:\\.[0-9]+)?|null|true|false)");

            return m.Success ? m.Groups[1].Value : "null";
        }

        /// <summary>
        /// Extrae el valor de una clave de texto de un JSON sin depender de una
        /// libreria externa. Devuelve null si la clave no existe.
        /// </summary>
        public static string ExtractJsonString(string body, string key)
        {
            if (string.IsNullOrEmpty(body) || string.IsNullOrEmpty(key))
            {
                return null;
            }

            int keyIndex = body.IndexOf("\"" + key + "\"", StringComparison.Ordinal);
            if (keyIndex < 0)
            {
                return null;
            }

            int colon = body.IndexOf(':', keyIndex + key.Length + 2);
            if (colon < 0)
            {
                return null;
            }

            int i = colon + 1;
            while (i < body.Length && char.IsWhiteSpace(body[i]))
            {
                i++;
            }

            if (i >= body.Length || body[i] != '"')
            {
                return null;
            }

            i++;
            StringBuilder sb = new StringBuilder();

            while (i < body.Length)
            {
                char c = body[i];

                if (c == '"')
                {
                    break;
                }

                if (c == '\\' && i + 1 < body.Length)
                {
                    char n = body[i + 1];

                    switch (n)
                    {
                        case '"': sb.Append('"'); i += 2; break;
                        case '\\': sb.Append('\\'); i += 2; break;
                        case '/': sb.Append('/'); i += 2; break;
                        case 'b': sb.Append('\b'); i += 2; break;
                        case 'f': sb.Append('\f'); i += 2; break;
                        case 'n': sb.Append('\n'); i += 2; break;
                        case 'r': sb.Append('\r'); i += 2; break;
                        case 't': sb.Append('\t'); i += 2; break;
                        case 'u':
                            if (i + 5 < body.Length)
                            {
                                int code;
                                if (int.TryParse(body.Substring(i + 2, 4),
                                        NumberStyles.HexNumber,
                                        CultureInfo.InvariantCulture,
                                        out code))
                                {
                                    sb.Append((char)code);
                                    i += 6;
                                    break;
                                }
                            }
                            sb.Append(n);
                            i += 2;
                            break;
                        default:
                            sb.Append(n);
                            i += 2;
                            break;
                    }

                    continue;
                }

                sb.Append(c);
                i++;
            }

            return sb.ToString();
        }

        public static string ExtractReceiptXml(string body)
        {
            if (string.IsNullOrEmpty(body))
            {
                return null;
            }

            string trimmed = body.TrimStart();
            bool looksLikeJson = trimmed.StartsWith("{") || trimmed.StartsWith("[");

            // En JSON los "<" pueden venir escapados como \u003c; se desescapa el
            // cuerpo completo (tambien convierte \n, \", \\ ...).
            string source = looksLikeJson ? UnescapeJson(body) : body;

            int start = source.IndexOf("<receipt", StringComparison.OrdinalIgnoreCase);
            if (start < 0)
            {
                return null;
            }

            int end = source.IndexOf("</receipt>", start, StringComparison.OrdinalIgnoreCase);
            if (end >= 0)
            {
                return source.Substring(start, end + "</receipt>".Length - start);
            }

            int last = source.LastIndexOf('>');
            if (last < start)
            {
                return null;
            }

            return source.Substring(start, last - start + 1);
        }

        public static string UnescapeJson(string s)
        {
            if (string.IsNullOrEmpty(s) || s.IndexOf('\\') < 0)
            {
                return s;
            }

            StringBuilder sb = new StringBuilder(s.Length);

            for (int i = 0; i < s.Length; i++)
            {
                char c = s[i];
                if (c != '\\' || i + 1 >= s.Length)
                {
                    sb.Append(c);
                    continue;
                }

                char n = s[++i];
                switch (n)
                {
                    case '"': sb.Append('"'); break;
                    case '\\': sb.Append('\\'); break;
                    case '/': sb.Append('/'); break;
                    case 'b': sb.Append('\b'); break;
                    case 'f': sb.Append('\f'); break;
                    case 'n': sb.Append('\n'); break;
                    case 'r': sb.Append('\r'); break;
                    case 't': sb.Append('\t'); break;
                    case 'u':
                        if (i + 4 < s.Length)
                        {
                            int code;
                            if (int.TryParse(s.Substring(i + 1, 4),
                                    NumberStyles.HexNumber,
                                    CultureInfo.InvariantCulture,
                                    out code))
                            {
                                sb.Append((char)code);
                                i += 4;
                                break;
                            }
                        }
                        sb.Append('\\').Append(n);
                        break;
                    default:
                        sb.Append('\\').Append(n);
                        break;
                }
            }

            return sb.ToString();
        }

        public static string EscapeJson(string s)
        {
            if (string.IsNullOrEmpty(s))
            {
                return "";
            }

            StringBuilder sb = new StringBuilder(s.Length + 8);
            foreach (char c in s)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (c < ' ')
                        {
                            sb.Append("\\u").Append(((int)c).ToString("x4", CultureInfo.InvariantCulture));
                        }
                        else
                        {
                            sb.Append(c);
                        }
                        break;
                }
            }
            return sb.ToString();
        }

        // ------------------------------------------------------------------
        // Interpretacion del XML
        // ------------------------------------------------------------------

        public static ReceiptDocument ParseXml(string xml)
        {
            ReceiptDocument result = new ReceiptDocument();
            result.RawXml = xml ?? "";

            if (string.IsNullOrEmpty(xml) || xml.Trim().Length == 0)
            {
                Log.Write("El ticket esta vacio.");
                return result;
            }

            string cleaned = xml.Replace("&nbsp;", " ");
            XmlDocument doc = null;

            try
            {
                XmlReaderSettings settings = new XmlReaderSettings();
                settings.DtdProcessing = DtdProcessing.Ignore;
                settings.XmlResolver = null;
                settings.IgnoreWhitespace = false;

                doc = new XmlDocument();
                doc.XmlResolver = null;
                doc.PreserveWhitespace = true;

                using (StringReader sr = new StringReader(cleaned))
                using (XmlReader xr = XmlReader.Create(sr, settings))
                {
                    doc.Load(xr);
                }
            }
            catch (Exception ex)
            {
                Log.Write("XML del ticket no valido ({0}); se imprime como texto plano.", ex.Message);
                BuildPlainText(result, cleaned);
                return result;
            }

            try
            {
                XmlElement root = doc.DocumentElement;
                if (root == null)
                {
                    throw new InvalidOperationException("XML sin elemento raiz");
                }

                bool isOrder = cleaned.IndexOf("<img", StringComparison.OrdinalIgnoreCase) < 0;
                result.DocumentType = isOrder ? "order" : "ticket";

                AddHeader(result, doc, isOrder);
                result.Elements.Add(ReceiptElement.Spacer());

                bool isInvoice = AddInvoiceLines(result, doc);
                if (isInvoice)
                {
                    result.Elements.Add(ReceiptElement.Row("", "--------", false));
                }

                AddFooter(result, doc, isInvoice);

                result.Parsed = true;
            }
            catch (Exception ex)
            {
                Log.Write("Error interpretando el ticket: {0}", ex.Message);
                result.Elements.Clear();
                BuildPlainText(result, cleaned);
            }

            if (result.Elements.Count == 0)
            {
                BuildPlainText(result, cleaned);
            }

            return result;
        }

        private static void AddHeader(ReceiptDocument result, XmlDocument doc, bool isOrder)
        {
            HashSet<string> seen = new HashSet<string>(StringComparer.Ordinal);
            XmlNodeList headerNodes = doc.SelectNodes("/receipt/div/div");

            if (headerNodes != null)
            {
                foreach (XmlNode node in headerNodes)
                {
                    string text = Clean(node.InnerText);
                    if (text.Length == 0)
                    {
                        continue;
                    }

                    if (text.IndexOf("----", StringComparison.Ordinal) >= 0 && HasElementChildren(node))
                    {
                        // Bloque "servido por..." con varias lineas dentro de otro div.
                        foreach (XmlNode child in node.ChildNodes)
                        {
                            string childText = Clean(child.InnerText);
                            if (childText.Length == 0 || IsOnlyDashes(childText))
                            {
                                continue;
                            }

                            if (seen.Add(childText))
                            {
                                result.Elements.Add(ReceiptElement.Centered(childText));
                            }
                        }
                    }
                    else if (!IsOnlyDashes(text))
                    {
                        if (seen.Add(text))
                        {
                            result.Elements.Add(ReceiptElement.Centered(text));
                        }
                    }
                }
            }

            if (isOrder)
            {
                XmlNodeList divs = doc.SelectNodes("/receipt/div");
                if (divs != null)
                {
                    foreach (XmlNode node in divs)
                    {
                        // Las lineas de factura ya se procesan aparte (div line-ratio).
                        if (node.Attributes != null && node.Attributes["line-ratio"] != null)
                        {
                            continue;
                        }

                        foreach (string line in SplitLines(node.InnerText))
                        {
                            if (IsOnlyDashes(line))
                            {
                                continue;
                            }

                            if (seen.Add(line))
                            {
                                result.Elements.Add(ReceiptElement.LeftAligned(line));
                            }
                        }
                    }
                }
            }
        }

        private static bool AddInvoiceLines(ReceiptDocument result, XmlDocument doc)
        {
            bool isInvoice = false;
            XmlNodeList lines = doc.SelectNodes("/receipt/div[@line-ratio='0.6']/line");

            if (lines == null)
            {
                return false;
            }

            foreach (XmlNode line in lines)
            {
                string left = null;

                foreach (XmlNode child in line.ChildNodes)
                {
                    if (child.NodeType != XmlNodeType.Element)
                    {
                        continue;
                    }

                    if (IsNamed(child, "left"))
                    {
                        left = Clean(child.InnerText);
                        isInvoice = true;
                    }
                    else if (IsNamed(child, "right"))
                    {
                        string right = FormatAmount(Clean(child.InnerText));
                        result.Elements.Add(ReceiptElement.Row(left ?? "", right, false));
                        left = null;
                        isInvoice = true;
                    }
                }

                if (!string.IsNullOrEmpty(left))
                {
                    result.Elements.Add(ReceiptElement.LeftAligned(left));
                }
            }

            return isInvoice;
        }

        private static void AddFooter(ReceiptDocument result, XmlDocument doc, bool isInvoice)
        {
            XmlNodeList lines = doc.SelectNodes("/receipt/line");
            if (lines == null)
            {
                return;
            }

            foreach (XmlNode line in lines)
            {
                string text = Clean(line.InnerText);
                if (IsOnlyDashes(text))
                {
                    continue;
                }

                bool hasElements = false;
                foreach (XmlNode child in line.ChildNodes)
                {
                    if (child.NodeType == XmlNodeType.Element)
                    {
                        hasElements = true;
                        break;
                    }
                }

                bool bold = text.IndexOf("TOTAL", StringComparison.OrdinalIgnoreCase) >= 0;

                if (hasElements && isInvoice)
                {
                    string left = null;
                    bool added = false;

                    foreach (XmlNode child in line.ChildNodes)
                    {
                        if (child.NodeType != XmlNodeType.Element)
                        {
                            continue;
                        }

                        if (IsNamed(child, "left"))
                        {
                            left = Clean(child.InnerText);
                            added = true;
                        }
                        else if (IsNamed(child, "right"))
                        {
                            result.Elements.Add(
                                ReceiptElement.Row(left ?? "", FormatAmount(Clean(child.InnerText)), bold));
                            left = null;
                            added = true;
                        }
                    }

                    if (!string.IsNullOrEmpty(left))
                    {
                        result.Elements.Add(ReceiptElement.LeftAligned(left, bold));
                        added = true;
                    }

                    if (!added)
                    {
                        AddTextLines(result, text);
                    }
                }
                else
                {
                    AddTextLines(result, text);
                }
            }
        }

        // ------------------------------------------------------------------
        // Utilidades
        // ------------------------------------------------------------------

        private static bool IsNamed(XmlNode node, string name)
        {
            return string.Equals(node.Name, name, StringComparison.OrdinalIgnoreCase);
        }

        private static bool HasElementChildren(XmlNode node)
        {
            foreach (XmlNode child in node.ChildNodes)
            {
                if (child.NodeType == XmlNodeType.Element)
                {
                    return true;
                }
            }
            return false;
        }

        private static void AddTextLines(ReceiptDocument result, string text)
        {
            if (string.IsNullOrEmpty(text))
            {
                return;
            }

            foreach (string line in SplitLines(text))
            {
                result.Elements.Add(ReceiptElement.LeftAligned(line));
            }
        }

        private static List<string> SplitLines(string text)
        {
            List<string> lines = new List<string>();

            if (string.IsNullOrEmpty(text))
            {
                return lines;
            }

            string[] parts = text.Replace("\r\n", "\n").Replace('\r', '\n').Split('\n');

            foreach (string part in parts)
            {
                string line = Clean(part);
                if (line.Length > 0)
                {
                    lines.Add(line);
                }
            }

            if (lines.Count == 0)
            {
                string single = Clean(text);
                if (single.Length > 0)
                {
                    lines.Add(single);
                }
            }

            return lines;
        }

        private static void BuildPlainText(ReceiptDocument result, string xml)
        {
            result.DocumentType = "text";
            result.Elements.Clear();

            string text = Regex.Replace(xml, "<[^>]+>", " ");
            text = DecodeEntities(text);
            AddTextLines(result, text);

            if (result.Elements.Count == 0)
            {
                result.Elements.Add(ReceiptElement.LeftAligned(Clean(text)));
            }
        }

        private static string DecodeEntities(string text)
        {
            try
            {
                return System.Net.WebUtility.HtmlDecode(text);
            }
            catch
            {
                return text;
            }
        }

        private static string Clean(string text)
        {
            if (string.IsNullOrEmpty(text))
            {
                return "";
            }

            StringBuilder sb = new StringBuilder(text.Length);
            bool space = false;

            foreach (char c in text)
            {
                if (c == '\r' || c == '\n' || c == '\t' || c == '\u00A0' || char.IsWhiteSpace(c))
                {
                    space = true;
                    continue;
                }

                if (c < ' ' || c == '\uFFFD')
                {
                    space = true;
                    continue;
                }

                if (space && sb.Length > 0)
                {
                    sb.Append(' ');
                }

                sb.Append(c);
                space = false;
            }

            return sb.ToString().Trim();
        }

        private static bool IsOnlyDashes(string text)
        {
            if (string.IsNullOrEmpty(text) || text.IndexOf('-') < 0)
            {
                return false;
            }

            foreach (char c in text)
            {
                if (c != '-' && c != ' ' && c != '.' && c != '=' && c != '_' && c != '\u00A0')
                {
                    return false;
                }
            }

            return true;
        }

        private static string FormatAmount(string value)
        {
            if (string.IsNullOrEmpty(value))
            {
                return "";
            }

            double number;

            if (double.TryParse(value, NumberStyles.Number, CultureInfo.InvariantCulture, out number))
            {
                return number.ToString("0.00", CultureInfo.InvariantCulture);
            }

            if (double.TryParse(value, NumberStyles.Number, CultureInfo.CurrentCulture, out number))
            {
                return number.ToString("0.00", CultureInfo.InvariantCulture);
            }

            return value;
        }
    }
}
