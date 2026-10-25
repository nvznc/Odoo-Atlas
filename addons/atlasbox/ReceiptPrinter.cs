using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Printing;
using System.Drawing.Text;

namespace JPosBox
{
    /// <summary>
    /// Dibuja un ticket sobre cualquier impresora instalada en Windows
    /// (no necesita impresora ESC/POS ni drivers especiales).
    /// </summary>
    public class ReceiptPrinter : IDisposable
    {
        private readonly List<ReceiptElement> _elements;
        private readonly float _fontSize;
        private readonly int _paperWidthMm;

        private Font _font;
        private Font _fontBold;
        private float _lineHeight;

        private StringFormat _fmtLeft;
        private StringFormat _fmtCenter;
        private StringFormat _fmtRight;

        private int _index;
        private float _y;

        public ReceiptPrinter(List<ReceiptElement> elements, float fontSize, int paperWidthMm)
        {
            _elements = elements ?? new List<ReceiptElement>();
            _fontSize = fontSize > 0 ? fontSize : 8.5f;
            _paperWidthMm = paperWidthMm;

            _fmtLeft = new StringFormat(StringFormatFlags.NoWrap);
            _fmtLeft.Alignment = StringAlignment.Near;
            _fmtLeft.LineAlignment = StringAlignment.Near;

            _fmtCenter = new StringFormat(StringFormatFlags.NoWrap);
            _fmtCenter.Alignment = StringAlignment.Center;
            _fmtCenter.LineAlignment = StringAlignment.Near;

            _fmtRight = new StringFormat(StringFormatFlags.NoWrap);
            _fmtRight.Alignment = StringAlignment.Far;
            _fmtRight.LineAlignment = StringAlignment.Near;
        }

        // ------------------------------------------------------------------
        // Impresion
        // ------------------------------------------------------------------

        public bool Print(string printerName)
        {
            return Print(printerName, null);
        }

        /// <summary>
        /// Imprime el ticket. Si printToFile no es nulo, el driver escribe la salida
        /// en ese archivo (util para "Microsoft Print to PDF").
        /// </summary>
        public bool Print(string printerName, string printToFile)
        {
            if (IsNoPrinter(printerName))
            {
                Log.Write("No hay impresora configurada; el ticket no se imprime.");
                return false;
            }

            if (PrintOutput.IsPdfPrinter(printerName) && string.IsNullOrEmpty(printToFile))
            {
                Log.Write("La impresora '{0}' es PDF y no hay archivo de salida. " +
                          "Configura PdfOutputDir o usa --print-pdf.", printerName);
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

                    pd.DocumentName = "jPosBox ticket";
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

                    _index = 0;
                    pd.PrintPage += OnPrintPage;
                    pd.Print();
                }

                Log.Write("Ticket enviado a '{0}' ({1} elementos).", printerName, _elements.Count);
                if (!string.IsNullOrEmpty(printToFile))
                {
                    Log.Write("Salida escrita en '{0}'.", printToFile);
                }
                return true;
            }
            catch (Exception ex)
            {
                Log.Write("Error al imprimir en '{0}': {1}", printerName, ex.Message);
                return false;
            }
        }

        private static bool IsNoPrinter(string printerName)
        {
            return string.IsNullOrEmpty(printerName)
                || printerName.Equals("nada", StringComparison.OrdinalIgnoreCase)
                || printerName.Equals("(sin impresora)", StringComparison.OrdinalIgnoreCase);
        }

        private static int MmToHundredths(int mm)
        {
            return (int)Math.Round(mm / 25.4 * 100.0);
        }

        private void OnPrintPage(object sender, PrintPageEventArgs e)
        {
            Graphics g = e.Graphics;
            g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit;
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

            float inset = 5f; // ~1.3 mm de margen de seguridad
            float x = area.Left + inset;
            float width = area.Width - inset * 2f;
            float top = area.Top + inset;
            float bottom = area.Bottom - inset;

            if (width < 40f)
            {
                width = area.Width;
            }

            EnsureFonts(g);

            _y = top;

            while (_index < _elements.Count)
            {
                ReceiptElement element = _elements[_index];
                float height = Measure(g, element, width);

                if (_y + height > bottom && _y > top + 0.01f)
                {
                    e.HasMorePages = true;
                    return;
                }

                Draw(g, element, x, width, _y);
                _y += height;
                _index++;
            }

            e.HasMorePages = false;
        }

        // ------------------------------------------------------------------
        // Previsualizacion (utilidad: --render)
        // ------------------------------------------------------------------

        public Bitmap RenderPreview(int widthPx)
        {
            int width = widthPx > 100 ? widthPx : 576;
            int height = 6000;

            Bitmap canvas = new Bitmap(width, height);
            float margin = Math.Max(6f, width * 0.02f);
            float contentWidth = width - margin * 2f;
            float y = margin;

            try
            {
                using (Graphics g = Graphics.FromImage(canvas))
                {
                    g.Clear(Color.White);
                    g.TextRenderingHint = TextRenderingHint.AntiAliasGridFit;
                    g.SmoothingMode = SmoothingMode.AntiAlias;

                    EnsureFonts(g);

                    for (int i = 0; i < _elements.Count; i++)
                    {
                        ReceiptElement element = _elements[i];
                        float h = Measure(g, element, contentWidth);
                        if (y + h > height - margin)
                        {
                            break;
                        }
                        Draw(g, element, margin, contentWidth, y);
                        y += h;
                    }
                }

                int used = (int)Math.Ceiling(y + margin);
                if (used < 1) used = 1;
                if (used > height) used = height;

                Bitmap result = new Bitmap(width, used);
                using (Graphics g2 = Graphics.FromImage(result))
                {
                    g2.Clear(Color.White);
                    g2.DrawImage(canvas,
                        new Rectangle(0, 0, width, used),
                        new Rectangle(0, 0, width, used),
                        GraphicsUnit.Pixel);
                }
                return result;
            }
            finally
            {
                canvas.Dispose();
            }
        }

        // ------------------------------------------------------------------
        // Dibujo
        // ------------------------------------------------------------------

        private void EnsureFonts(Graphics g)
        {
            if (_font != null)
            {
                return;
            }

            _font = new Font("Arial", _fontSize, FontStyle.Regular, GraphicsUnit.Point);
            _fontBold = new Font(_font, FontStyle.Bold);
            _lineHeight = _font.GetHeight(g) * 1.12f;
        }

        private float Measure(Graphics g, ReceiptElement element, float width)
        {
            EnsureFonts(g);

            Font font = element.Bold ? _fontBold : _font;

            if (element.Kind == ReceiptElementKind.Divider)
            {
                return _lineHeight * 0.8f;
            }

            if (element.Kind == ReceiptElementKind.Spacer)
            {
                return _lineHeight * 0.5f;
            }

            if (element.Kind == ReceiptElementKind.Row)
            {
                float rightWidth = string.IsNullOrEmpty(element.Right)
                    ? 0f
                    : g.MeasureString(element.Right, font).Width;

                float leftWidth = Math.Max(10f, width - rightWidth - 6f);
                int lines = Wrap(g, element.Text, font, leftWidth).Count;
                return Math.Max(1, lines) * _lineHeight;
            }

            int count = Wrap(g, element.Text, font, width).Count;
            return Math.Max(1, count) * _lineHeight;
        }

        private void Draw(Graphics g, ReceiptElement element, float x, float width, float y)
        {
            EnsureFonts(g);
            Font font = element.Bold ? _fontBold : _font;

            if (element.Kind == ReceiptElementKind.Divider)
            {
                using (Pen pen = new Pen(Color.DimGray, 1f))
                {
                    g.DrawLine(pen, x, y + _lineHeight * 0.4f, x + width, y + _lineHeight * 0.4f);
                }
                return;
            }

            if (element.Kind == ReceiptElementKind.Spacer)
            {
                return;
            }

            if (element.Kind == ReceiptElementKind.Row)
            {
                float rightWidth = string.IsNullOrEmpty(element.Right)
                    ? 0f
                    : g.MeasureString(element.Right, font).Width;

                float leftWidth = Math.Max(10f, width - rightWidth - 6f);

                if (!string.IsNullOrEmpty(element.Right))
                {
                    g.DrawString(element.Right, font, Brushes.Black,
                        new RectangleF(x, y, width, _lineHeight + 2f), _fmtRight);
                }

                List<string> lines = Wrap(g, element.Text, font, leftWidth);
                for (int i = 0; i < lines.Count; i++)
                {
                    g.DrawString(lines[i], font, Brushes.Black,
                        new RectangleF(x, y + i * _lineHeight, leftWidth, _lineHeight + 2f), _fmtLeft);
                }
                return;
            }

            bool centered = element.Kind == ReceiptElementKind.Center;
            StringFormat format = centered ? _fmtCenter : _fmtLeft;
            List<string> wrapped = Wrap(g, element.Text, font, width);

            for (int i = 0; i < wrapped.Count; i++)
            {
                g.DrawString(wrapped[i], font, Brushes.Black,
                    new RectangleF(x, y + i * _lineHeight, width, _lineHeight + 2f), format);
            }
        }

        private List<string> Wrap(Graphics g, string text, Font font, float width)
        {
            List<string> lines = new List<string>();

            if (string.IsNullOrEmpty(text))
            {
                lines.Add("");
                return lines;
            }

            string[] words = text.Split(new char[] { ' ', '\t' }, StringSplitOptions.RemoveEmptyEntries);
            string current = "";

            foreach (string word in words)
            {
                string candidate = current.Length == 0 ? word : current + " " + word;

                if (g.MeasureString(candidate, font).Width <= width)
                {
                    current = candidate;
                    continue;
                }

                if (current.Length > 0)
                {
                    lines.Add(current);
                    current = "";
                }

                string rest = word;
                while (rest.Length > 1 && g.MeasureString(rest, font).Width > width)
                {
                    int cut = rest.Length;

                    while (cut > 1 && g.MeasureString(rest.Substring(0, cut), font).Width > width)
                    {
                        cut--;
                    }

                    lines.Add(rest.Substring(0, cut));
                    rest = rest.Substring(cut);
                }

                current = rest;
            }

            if (current.Length > 0)
            {
                lines.Add(current);
            }

            if (lines.Count == 0)
            {
                lines.Add(text);
            }

            return lines;
        }

        public void Dispose()
        {
            if (_fmtLeft != null) { _fmtLeft.Dispose(); _fmtLeft = null; }
            if (_fmtCenter != null) { _fmtCenter.Dispose(); _fmtCenter = null; }
            if (_fmtRight != null) { _fmtRight.Dispose(); _fmtRight = null; }
            if (_fontBold != null) { _fontBold.Dispose(); _fontBold = null; }
            if (_font != null) { _font.Dispose(); _font = null; }
        }
    }
}
