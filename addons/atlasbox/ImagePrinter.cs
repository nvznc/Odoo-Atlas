using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Printing;
using System.IO;

namespace JPosBox
{
    /// <summary>
    /// Imprime una imagen (la comanda rasterizada que envia el modulo jIotBox de
    /// Odoo) en cualquier impresora de Windows, repartiendo en varias paginas si
    /// la imagen es mas alta que la pagina.
    /// </summary>
    public class ImagePrinter
    {
        private readonly Image _image;
        private readonly int _paperWidthMm;

        private float _sourceY;
        private int _pageCount;

        public ImagePrinter(Image image, int paperWidthMm)
        {
            _image = image;
            _paperWidthMm = paperWidthMm;
        }

        public bool Print(string printerName)
        {
            return Print(printerName, null);
        }

        public bool Print(string printerName, string printToFile)
        {
            if (string.IsNullOrEmpty(printerName)
                || printerName.Equals("nada", StringComparison.OrdinalIgnoreCase)
                || printerName.Equals("(sin impresora)", StringComparison.OrdinalIgnoreCase))
            {
                Log.Write("No hay impresora configurada; la comanda no se imprime.");
                return false;
            }

            if (PrintOutput.IsPdfPrinter(printerName) && string.IsNullOrEmpty(printToFile))
            {
                Log.Write("La impresora '{0}' es PDF y no hay archivo de salida. " +
                          "Configura PdfOutputDir o usa --print-pdf.", printerName);
                return false;
            }

            if (_image == null || _image.Width <= 0 || _image.Height <= 0)
            {
                Log.Write("La imagen de la comanda no es valida.");
                return false;
            }

            try
            {
                using (PrintDocument pd = new PrintDocument())
                {
                    pd.PrinterSettings.PrinterName = printerName;

                    if (!pd.PrinterSettings.IsValid)
                    {
                        Log.Write("La impresora '{0}' no existe en este sistema.", printerName);
                        return false;
                    }

                    if (!string.IsNullOrEmpty(printToFile))
                    {
                        pd.PrinterSettings.PrintToFile = true;
                        pd.PrinterSettings.PrintFileName = printToFile;
                    }

                    pd.DocumentName = "jPosBox comanda";
                    pd.PrintController = new StandardPrintController();

                    try
                    {
                        pd.DefaultPageSettings.Margins = new Margins(0, 0, 0, 0);
                    }
                    catch
                    {
                    }

                    if (_paperWidthMm > 0)
                    {
                        try
                        {
                            pd.DefaultPageSettings.PaperSize = new PaperSize(
                                "jPosBox",
                                MmToHundredths(_paperWidthMm),
                                MmToHundredths(297));
                        }
                        catch (Exception ex)
                        {
                            Log.Write("No se pudo fijar el ancho de papel ({0}); se usa el del driver.", ex.Message);
                        }
                    }

                    _sourceY = 0;
                    _pageCount = 0;
                    pd.PrintPage += OnPrintPage;
                    pd.Print();
                }

                Log.Write("Comanda enviada a '{0}' ({1} pagina(s), imagen {2}x{3}).",
                    printerName, _pageCount, _image.Width, _image.Height);

                if (!string.IsNullOrEmpty(printToFile))
                {
                    Log.Write("Salida escrita en '{0}'.", printToFile);
                }

                return true;
            }
            catch (Exception ex)
            {
                Log.Write("Error al imprimir la comanda en '{0}': {1}", printerName, ex.Message);
                return false;
            }
        }

        private static int MmToHundredths(int mm)
        {
            return (int)Math.Round(mm / 25.4 * 100.0);
        }

        private void OnPrintPage(object sender, PrintPageEventArgs e)
        {
            Graphics g = e.Graphics;
            g.InterpolationMode = InterpolationMode.HighQualityBicubic;
            g.PixelOffsetMode = PixelOffsetMode.HighQuality;
            g.SmoothingMode = SmoothingMode.AntiAlias;

            RectangleF area = e.MarginBounds;

            if (area.Width < 40f || area.Height < 40f)
            {
                area = e.PageBounds;
            }
            if (area.Width < 40f)
            {
                area = new RectangleF(0, 0, Math.Max(100f, e.PageBounds.Width), Math.Max(100f, e.PageBounds.Height));
            }

            float inset = 5f;
            float x = area.Left + inset;
            float y = area.Top + inset;
            float width = area.Width - inset * 2f;
            float height = area.Height - inset * 2f;

            if (width < 40f)
            {
                width = area.Width;
            }

            float scale = width / _image.Width;
            float sourcePageHeight = height / scale;

            if (sourcePageHeight < 1f)
            {
                sourcePageHeight = 1f;
            }

            float remaining = _image.Height - _sourceY;

            if (remaining <= 0f)
            {
                e.HasMorePages = false;
                return;
            }

            float sourceHeight = Math.Min(sourcePageHeight, remaining);

            g.DrawImage(
                _image,
                new RectangleF(x, y, width, sourceHeight * scale),
                new RectangleF(0, _sourceY, _image.Width, sourceHeight),
                GraphicsUnit.Pixel);

            _sourceY += sourceHeight;
            _pageCount++;
            e.HasMorePages = _sourceY < _image.Height - 0.01f;
        }
    }
}
