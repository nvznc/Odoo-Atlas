using System;
using System.IO;
using System.Text;

namespace JPosBox
{
    /// <summary>
    /// Registro sencillo en archivo y notificacion a la interfaz.
    /// </summary>
    public static class Log
    {
        private static readonly object Sync = new object();
        private static string _file;

        /// <summary>Se dispara con cada mensaje (la interfaz lo usa para la barra de estado).</summary>
        public static event Action<string> Message;

        public static string FilePath
        {
            get { return _file; }
        }

        public static void Init(string dir)
        {
            try
            {
                Directory.CreateDirectory(dir);
                _file = Path.Combine(dir, "atlasbox.log");
                FileInfo info = new FileInfo(_file);
                if (info.Exists && info.Length > 2 * 1024 * 1024)
                {
                    try { File.Delete(_file + ".old"); }
                    catch { }
                    try { File.Move(_file, _file + ".old"); }
                    catch { }
                }
            }
            catch
            {
                _file = null;
            }
        }

        public static void Write(string format, params object[] args)
        {
            string text = (args != null && args.Length > 0)
                ? string.Format(format, args)
                : format;

            string line = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + "  " + text;

            lock (Sync)
            {
                try
                {
                    if (_file != null)
                    {
                        File.AppendAllText(_file, line + Environment.NewLine, Encoding.UTF8);
                    }
                }
                catch
                {
                    // Nunca debe romper la aplicacion por no poder escribir el log.
                }
            }

            Action<string> handler = Message;
            if (handler != null)
            {
                try { handler(text); }
                catch { }
            }
        }
    }
}
