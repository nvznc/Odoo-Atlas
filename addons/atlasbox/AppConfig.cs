using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;

namespace JPosBox
{
    /// <summary>
    /// Configuracion en un INI simple (sustituye a la base de datos Derby del original).
    /// </summary>
    public class AppConfig
    {
        private readonly Dictionary<string, string> _values =
            new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        public string Dir { get; private set; }
        public string FilePath { get; private set; }

        public AppConfig()
        {
            Dir = ResolveDir();
            FilePath = Path.Combine(Dir, "jposbox.ini");
            Load();

            if (!File.Exists(FilePath))
            {
                ApplyDefaults();
                Save();
            }
        }

        private void ApplyDefaults()
        {
            PosBoxes = 0;
            Auto = false;
            Printer1 = "nada";
            Printer2 = "nada";
            Port1 = 8069;
            Port2 = 8070;
            FontSize = 8.5f;
            PaperWidthMm = 0;
            PdfOutputDir = "";
        }

        private static string ResolveDir()
        {
            // Permite modo portable: JPOSBOX_HOME=C:\ruta\jposbox
            string env = Environment.GetEnvironmentVariable("JPOSBOX_HOME");
            if (!string.IsNullOrEmpty(env))
            {
                return env;
            }

            return Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                "jPosBox");
        }

        public void Load()
        {
            _values.Clear();
            try
            {
                if (!File.Exists(FilePath))
                {
                    return;
                }

                foreach (string raw in File.ReadAllLines(FilePath, Encoding.UTF8))
                {
                    string line = raw.Trim();
                    if (line.Length == 0 || line.StartsWith("#") || line.StartsWith(";"))
                    {
                        continue;
                    }

                    int eq = line.IndexOf('=');
                    if (eq <= 0)
                    {
                        continue;
                    }

                    string key = line.Substring(0, eq).Trim();
                    string value = line.Substring(eq + 1).Trim();
                    _values[key] = value;
                }
            }
            catch (Exception ex)
            {
                Log.Write("No se pudo leer la configuracion: {0}", ex.Message);
            }
        }

        public void Save()
        {
            try
            {
                Directory.CreateDirectory(Dir);

                List<string> keys = new List<string>(_values.Keys);
                keys.Sort(StringComparer.OrdinalIgnoreCase);

                StringBuilder sb = new StringBuilder();
                sb.AppendLine("# jPosBox - configuracion");
                sb.AppendLine("# PosBoxes = 0 | 1 | 2");
                sb.AppendLine("# Auto = on | off   (arrancar los PosBoxes al abrir la aplicacion)");
                sb.AppendLine("# Printer1 / Printer2 = nombre exacto de la impresora de Windows, o nada");
                sb.AppendLine("# PortPrinter1 / PortPrinter2 = puerto HTTP");
                sb.AppendLine("# FontSize = tamano de letra en puntos (por defecto 8.5)");
                sb.AppendLine("# PaperWidthMm = ancho de papel en mm (0 = usar el del driver)");
                sb.AppendLine("# PdfOutputDir = carpeta donde guardar los PDF de prueba (vacio = desactivado)");
                sb.AppendLine();

                foreach (string key in keys)
                {
                    sb.Append(key).Append('=').AppendLine(_values[key] ?? "");
                }

                File.WriteAllText(FilePath, sb.ToString(), Encoding.UTF8);
            }
            catch (Exception ex)
            {
                Log.Write("No se pudo guardar la configuracion: {0}", ex.Message);
            }
        }

        public string Get(string key, string def)
        {
            string value;
            if (_values.TryGetValue(key, out value) && value != null && value.Length > 0)
            {
                return value;
            }
            return def;
        }

        public int GetInt(string key, int def)
        {
            int value;
            if (int.TryParse(Get(key, ""), NumberStyles.Integer, CultureInfo.InvariantCulture, out value))
            {
                return value;
            }
            return def;
        }

        public double GetDouble(string key, double def)
        {
            double value;
            string raw = Get(key, "").Replace(',', '.');
            if (double.TryParse(raw, NumberStyles.Float, CultureInfo.InvariantCulture, out value))
            {
                return value;
            }
            return def;
        }

        public bool GetBool(string key, bool def)
        {
            string value = Get(key, "").Trim().ToLowerInvariant();
            if (value == "on" || value == "true" || value == "1" || value == "si" || value == "yes")
            {
                return true;
            }
            if (value == "off" || value == "false" || value == "0" || value == "no")
            {
                return false;
            }
            return def;
        }

        public void Set(string key, string value)
        {
            _values[key] = value ?? "";
        }

        public void Set(string key, int value)
        {
            Set(key, value.ToString(CultureInfo.InvariantCulture));
        }

        public void Set(string key, bool value)
        {
            Set(key, value ? "on" : "off");
        }

        public int PosBoxes
        {
            get
            {
                int value = GetInt("PosBoxes", 0);
                if (value < 0) return 0;
                if (value > 2) return 2;
                return value;
            }
            set { Set("PosBoxes", value); }
        }

        public bool Auto
        {
            get { return GetBool("Auto", false); }
            set { Set("Auto", value); }
        }

        public string Printer1
        {
            get { return Get("Printer1", "nada"); }
            set { Set("Printer1", value); }
        }

        public string Printer2
        {
            get { return Get("Printer2", "nada"); }
            set { Set("Printer2", value); }
        }

        public int Port1
        {
            get { return GetInt("PortPrinter1", 8069); }
            set { Set("PortPrinter1", value); }
        }

        public int Port2
        {
            get { return GetInt("PortPrinter2", 8070); }
            set { Set("PortPrinter2", value); }
        }

        public float FontSize
        {
            get
            {
                double value = GetDouble("FontSize", 8.5);
                if (value < 3) value = 3;
                if (value > 30) value = 30;
                return (float)value;
            }
            set { Set("FontSize", value.ToString("0.0", CultureInfo.InvariantCulture)); }
        }

        public int PaperWidthMm
        {
            get
            {
                int value = GetInt("PaperWidthMm", 0);
                if (value < 0) value = 0;
                if (value > 300) value = 300;
                return value;
            }
            set { Set("PaperWidthMm", value); }
        }

        /// <summary>
        /// Carpeta donde se guardan los PDF cuando la impresora seleccionada es
        /// una impresora PDF (por ejemplo "Microsoft Print to PDF").
        /// Vacio = desactivado.
        /// </summary>
        public string PdfOutputDir
        {
            get { return Get("PdfOutputDir", ""); }
            set { Set("PdfOutputDir", value ?? ""); }
        }
    }
}
