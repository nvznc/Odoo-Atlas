using System;
using System.Drawing;
using System.Drawing.Imaging;
using System.IO;
using System.Text;
using System.Threading;
using System.Windows.Forms;

namespace JPosBox
{
    internal static class Program
    {
        [STAThread]
        private static int Main(string[] args)
        {
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            if (args.Length >= 3 && IsArg(args[0], "--render"))
            {
                return RenderCommand(args);
            }

            if (args.Length >= 2 && IsArg(args[0], "--print"))
            {
                return PrintCommand(args);
            }

            if (args.Length >= 3 && IsArg(args[0], "--print-pdf"))
            {
                return PrintPdfCommand(args);
            }

            string allowMultiple = Environment.GetEnvironmentVariable("JPOSBOX_ALLOW_MULTIPLE");

            if (allowMultiple == "1")
            {
                Application.Run(new MainForm());
                return 0;
            }

            bool created;
            using (Mutex mutex = new Mutex(true, "jPosBox.SingleInstance", out created))
            {
                if (!created)
                {
                    SignalExistingInstance();
                    return 0;
                }

                using (EventWaitHandle activation = new EventWaitHandle(
                    false, EventResetMode.AutoReset, "jPosBox.Activate"))
                {
                    MainForm form = new MainForm();

                    Thread watcher = new Thread(delegate()
                    {
                        try
                        {
                            while (!form.IsDisposed)
                            {
                                if (!activation.WaitOne(500))
                                {
                                    continue;
                                }

                                if (form.IsDisposed)
                                {
                                    break;
                                }

                                for (int i = 0; i < 20 && !form.IsHandleCreated; i++)
                                {
                                    Thread.Sleep(100);
                                }

                                try
                                {
                                    form.BeginInvoke(new Action(form.ShowFromTray));
                                }
                                catch (ObjectDisposedException)
                                {
                                    break;
                                }
                                catch (InvalidOperationException)
                                {
                                }
                            }
                        }
                        catch (ObjectDisposedException)
                        {
                        }
                    });

                    watcher.IsBackground = true;
                    watcher.Start();

                    Application.Run(form);
                }
            }

            return 0;
        }

        private static void SignalExistingInstance()
        {
            for (int attempt = 0; attempt < 20; attempt++)
            {
                try
                {
                    using (EventWaitHandle activation = EventWaitHandle.OpenExisting("jPosBox.Activate"))
                    {
                        activation.Set();
                        return;
                    }
                }
                catch (WaitHandleCannotBeOpenedException)
                {
                    Thread.Sleep(100);
                }
                catch (UnauthorizedAccessException)
                {
                    break;
                }
            }

            ShowAlreadyRunning();
        }

        private static void ShowAlreadyRunning()
        {
            MessageBox.Show(
                "Atlas-Box ya se esta ejecutando.\n\n" +
                "Busca el icono en la bandeja del sistema (junto al reloj).",
                "Atlas-Box",
                MessageBoxButtons.OK,
                MessageBoxIcon.Information);
        }

        private static bool IsArg(string value, string expected)
        {
            return string.Equals(value, expected, StringComparison.OrdinalIgnoreCase);
        }

        // ------------------------------------------------------------------
        // Utilidades de linea de comandos
        // ------------------------------------------------------------------

        private static int RenderCommand(string[] args)
        {
            string input = args[1];
            string output = args[2];
            int width = 576;

            if (args.Length >= 4)
            {
                int.TryParse(args[3], out width);
            }

            try
            {
                AppConfig config = new AppConfig();
                Log.Init(config.Dir);

                string xml = ReadReceipt(args[1]);
                if (xml == null)
                {
                    ShowError("El archivo no contiene un ticket valido:\n" + input);
                    return 2;
                }

                ReceiptDocument document = ReceiptParser.ParseXml(xml);

                using (ReceiptPrinter printer = new ReceiptPrinter(
                    document.Elements, config.FontSize, config.PaperWidthMm))
                using (Bitmap image = printer.RenderPreview(width))
                {
                    image.Save(output, ImageFormat.Png);
                }

                Log.Write("Vista previa generada: {0} ({1} elementos, tipo {2})",
                    output, document.Elements.Count, document.DocumentType);

                return 0;
            }
            catch (Exception ex)
            {
                ShowError("No se pudo generar la vista previa:\n" + ex.Message);
                return 1;
            }
        }

        private static int PrintCommand(string[] args)
        {
            try
            {
                AppConfig config = new AppConfig();
                Log.Init(config.Dir);

                string xml = ReadReceipt(args[1]);
                if (xml == null)
                {
                    ShowError("El archivo no contiene un ticket valido:\n" + args[1]);
                    return 2;
                }

                string printerName = args.Length >= 3 ? args[2] : config.Printer1;
                ReceiptDocument document = ReceiptParser.ParseXml(xml);

                using (ReceiptPrinter printer = new ReceiptPrinter(
                    document.Elements, config.FontSize, config.PaperWidthMm))
                {
                    bool ok = printer.Print(printerName);
                    if (!ok)
                    {
                        ShowError("No se pudo imprimir en '" + printerName + "'.\n\n" +
                            "Revisa el log en " + config.Dir);
                        return 3;
                    }
                }

                return 0;
            }
            catch (Exception ex)
            {
                ShowError("No se pudo imprimir:\n" + ex.Message);
                return 1;
            }
        }

        private static int PrintPdfCommand(string[] args)
        {
            string output = args[2];

            try
            {
                AppConfig config = new AppConfig();
                Log.Init(config.Dir);

                string xml = ReadReceipt(args[1]);
                if (xml == null)
                {
                    ShowError("El archivo no contiene un ticket valido:\n" + args[1]);
                    return 2;
                }

                string printerName = args.Length >= 4 ? args[3] : "Microsoft Print to PDF";
                ReceiptDocument document = ReceiptParser.ParseXml(xml);

                using (ReceiptPrinter printer = new ReceiptPrinter(
                    document.Elements, config.FontSize, config.PaperWidthMm))
                {
                    bool ok = printer.Print(printerName, output);
                    if (!ok)
                    {
                        ShowError("No se pudo generar el PDF con la impresora '" + printerName + "'.\n\n" +
                            "Revisa el log en " + config.Dir);
                        return 3;
                    }
                }

                return 0;
            }
            catch (Exception ex)
            {
                ShowError("No se pudo generar el PDF:\n" + ex.Message);
                return 1;
            }
        }

        private static string ReadReceipt(string path)
        {
            if (!File.Exists(path))
            {
                return null;
            }

            string text = File.ReadAllText(path, Encoding.UTF8);
            string xml = ReceiptParser.ExtractReceiptXml(text);

            return xml ?? (text.IndexOf("<receipt", StringComparison.OrdinalIgnoreCase) >= 0 ? text : null);
        }

        private static void ShowError(string message)
        {
            Log.Write(message.Replace("\n", " "));
            MessageBox.Show(message, "jPosBox", MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
    }
}
