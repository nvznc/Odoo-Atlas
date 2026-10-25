using System;
using System.Globalization;
using System.IO;
using System.Threading;

namespace JPosBox
{
    /// <summary>
    /// Decide si una impresion debe escribirse a un PDF de prueba en lugar de
    /// abrir el dialogo "Guardar como" de la impresora virtual.
    /// </summary>
    public static class PrintOutput
    {
        private static int _counter;

        public static bool IsPdfPrinter(string printerName)
        {
            return !string.IsNullOrEmpty(printerName)
                && printerName.IndexOf("PDF", StringComparison.OrdinalIgnoreCase) >= 0;
        }

        /// <summary>
        /// Devuelve la ruta del PDF a generar, o null si no corresponde.
        /// </summary>
        public static string Resolve(string dir, string printerName, string prefix)
        {
            if (string.IsNullOrEmpty(dir) || !IsPdfPrinter(printerName))
            {
                return null;
            }

            try
            {
                Directory.CreateDirectory(dir);

                int number = Interlocked.Increment(ref _counter);
                string stamp = DateTime.Now.ToString("yyyyMMdd-HHmmss-fff", CultureInfo.InvariantCulture);
                string name = prefix + "-" + stamp + "-" + number.ToString(CultureInfo.InvariantCulture) + ".pdf";

                return Path.Combine(dir, name);
            }
            catch (Exception ex)
            {
                Log.Write("No se pudo preparar la carpeta PDF '{0}': {1}", dir, ex.Message);
                return null;
            }
        }
    }
}
