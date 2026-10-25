using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Printing;
using System.Globalization;
using System.IO;
using System.Windows.Forms;
using Microsoft.Win32;

namespace JPosBox
{
    public class MainForm : Form
    {
        private const string RunKeyName = "jPosBox";
        private const string RunKeyPath = @"Software\Microsoft\Windows\CurrentVersion\Run";

        private readonly AppConfig _config;

        private TabControl _tabs;
        private TabPage _tabGeneral;
        private TabPage _tabBox1;
        private TabPage _tabBox2;

        private ComboBox _posBoxesCombo;
        private CheckBox _autoStartCheck;
        private CheckBox _runAtStartupCheck;
        private CheckBox _mainRefCheck;
        private CheckBox _saveReceiptsCheck;

        private ComboBox _printerCombo1;
        private ComboBox _printerCombo2;
        private TextBox _portBox1;
        private TextBox _portBox2;
        private TextBox _pdfDirBox;

        private Button _startButton1;
        private Button _stopButton1;
        private Button _startButton2;
        private Button _stopButton2;
        private Label _stateLabel1;
        private Label _stateLabel2;

        private ToolStripStatusLabel _statusLabel;

        private HwProxyServer _server1;
        private HwProxyServer _server2;
        private bool _closing;

        private NotifyIcon _trayIcon;
        private bool _reallyExit;
        private bool _trayHintShown;

        public MainForm()
        {
            _config = new AppConfig();
            Log.Init(_config.Dir);

            BuildUi();
            CreateTrayIcon();
            LoadPrinters();
            Log.Message += OnLogMessage;

            LoadSettings();

            FormClosing += MainFormClosing;

            Log.Write("Atlas-Box iniciado. Configuracion: {0}", _config.FilePath);
        }

        // ------------------------------------------------------------------
        // Construccion de la interfaz
        // ------------------------------------------------------------------

        private void BuildUi()
        {
            Text = "Atlas-Box";
            StartPosition = FormStartPosition.CenterScreen;
            FormBorderStyle = FormBorderStyle.FixedSingle;
            MaximizeBox = false;
            ClientSize = new Size(500, 420);
            Font = new Font("Segoe UI", 9f);

            _tabs = new TabControl();
            _tabs.SetBounds(10, 10, 480, 370);
            _tabs.Selecting += TabsSelecting;

            _tabGeneral = BuildGeneralTab();
            _tabBox1 = BuildBoxTab("Atlas-Box 1",
                out _printerCombo1, out _portBox1,
                out _startButton1, out _stopButton1, out _stateLabel1);

            _tabBox2 = BuildBoxTab("Atlas-Box 2",
                out _printerCombo2, out _portBox2,
                out _startButton2, out _stopButton2, out _stateLabel2);

            _tabs.TabPages.Add(_tabGeneral);
            _tabs.TabPages.Add(_tabBox1);
            _tabs.TabPages.Add(_tabBox2);
            Controls.Add(_tabs);

            StatusStrip strip = new StatusStrip();
            _statusLabel = new ToolStripStatusLabel("Listo");
            _statusLabel.AutoSize = false;
            _statusLabel.Spring = true;
            _statusLabel.TextAlign = ContentAlignment.MiddleLeft;
            strip.Items.Add(_statusLabel);

            Controls.Add(strip);
        }

        private TabPage BuildGeneralTab()
        {
            TabPage page = new TabPage("Atlas-Box");

            page.Controls.Add(MakeLabel("PosBoxes:", 12, 18));

            _posBoxesCombo = new ComboBox();
            _posBoxesCombo.DropDownStyle = ComboBoxStyle.DropDownList;
            _posBoxesCombo.SetBounds(95, 15, 60, 23);
            _posBoxesCombo.Items.AddRange(new object[] { "0", "1", "2" });
            page.Controls.Add(_posBoxesCombo);

            _autoStartCheck = MakeCheck("Iniciar los PosBoxes automaticamente", 12, 50, 380);
            page.Controls.Add(_autoStartCheck);

            _runAtStartupCheck = MakeCheck("Ejecutar Atlas-Box al iniciar Windows", 12, 78, 380);
            page.Controls.Add(_runAtStartupCheck);

            _mainRefCheck = MakeCheck("Imprimir referencia principal en vez de pedido", 12, 106, 420);
            _mainRefCheck.Enabled = false;
            page.Controls.Add(_mainRefCheck);

            _saveReceiptsCheck = MakeCheck("Guardar tickets para reimprimir", 12, 134, 380);
            _saveReceiptsCheck.Enabled = false;
            page.Controls.Add(_saveReceiptsCheck);

            page.Controls.Add(MakeButton("Guardar", 12, 175, 90, SaveClick, page));
            page.Controls.Add(MakeButton("Ver log", 110, 175, 90, LogClick, page));

            page.Controls.Add(MakeLabel("Carpeta PDF:", 12, 218));

            _pdfDirBox = new TextBox();
            _pdfDirBox.SetBounds(110, 215, 270, 23);
            page.Controls.Add(_pdfDirBox);
            page.Controls.Add(MakeButton("...", 385, 214, 35, BrowsePdfDirClick, page));

            Label pdfNote = MakeLabel(
                "Opcional. Si la impresora es PDF, guarda ahi cada ticket/comanda.",
                12, 245);
            pdfNote.ForeColor = Color.DimGray;
            page.Controls.Add(pdfNote);

            Label pathLabel = MakeLabel("Configuracion:", 12, 285);
            pathLabel.ForeColor = Color.DimGray;
            page.Controls.Add(pathLabel);

            Label pathValue = MakeLabel(_config.FilePath, 12, 303);
            pathValue.AutoSize = false;
            pathValue.SetBounds(12, 303, 440, 20);
            pathValue.ForeColor = Color.DimGray;
            page.Controls.Add(pathValue);

            return page;
        }

        private TabPage BuildBoxTab(string title,
            out ComboBox printerCombo, out TextBox portBox,
            out Button startButton, out Button stopButton, out Label stateLabel)
        {
            TabPage page = new TabPage(title);

            page.Controls.Add(MakeLabel("Impresora:", 12, 18));

            printerCombo = new ComboBox();
            printerCombo.DropDownStyle = ComboBoxStyle.DropDownList;
            printerCombo.SetBounds(95, 15, 340, 23);
            page.Controls.Add(printerCombo);

            page.Controls.Add(MakeLabel("Puerto:", 12, 58));

            portBox = new TextBox();
            portBox.SetBounds(95, 55, 70, 23);
            page.Controls.Add(portBox);

            page.Controls.Add(MakeButton("Guardar", 12, 100, 90, SaveClick, page));

            startButton = MakeButton("Iniciar", 270, 100, 85, StartClick, page);
            stopButton = MakeButton("Detener", 365, 100, 85, StopClick, page);
            stopButton.Enabled = false;

            stateLabel = MakeLabel("Detenido", 12, 145);
            stateLabel.ForeColor = Color.DimGray;
            page.Controls.Add(stateLabel);

            Label note = MakeLabel("Escucha en todas las interfaces de red del equipo.", 12, 175);
            note.ForeColor = Color.DimGray;
            page.Controls.Add(note);

            Label printerNote = MakeLabel(
                "Si no aparece tu impresora, instalala primero en Windows.",
                12, 197);
            printerNote.ForeColor = Color.DimGray;
            page.Controls.Add(printerNote);

            return page;
        }

        private static Label MakeLabel(string text, int x, int y)
        {
            Label label = new Label();
            label.Text = text;
            label.AutoSize = true;
            label.Location = new Point(x, y);
            return label;
        }

        private static CheckBox MakeCheck(string text, int x, int y, int width)
        {
            CheckBox check = new CheckBox();
            check.Text = text;
            check.AutoSize = false;
            check.SetBounds(x, y, width, 24);
            return check;
        }

        private static Button MakeButton(string text, int x, int y, int width,
            EventHandler handler, Control parent)
        {
            Button button = new Button();
            button.Text = text;
            button.SetBounds(x, y, width, 28);
            button.Click += handler;
            parent.Controls.Add(button);
            return button;
        }

        private void LoadPrinters()
        {
            _printerCombo1.Items.Add("(sin impresora)");
            _printerCombo2.Items.Add("(sin impresora)");

            try
            {
                List<string> names = new List<string>();
                foreach (string name in PrinterSettings.InstalledPrinters)
                {
                    names.Add(name);
                }

                names.Sort(StringComparer.CurrentCultureIgnoreCase);

                foreach (string name in names)
                {
                    _printerCombo1.Items.Add(name);
                    _printerCombo2.Items.Add(name);
                }
            }
            catch (Exception ex)
            {
                Log.Write("No se pudo enumerar las impresoras: {0}", ex.Message);
            }

            if (_printerCombo1.Items.Count == 1)
            {
                Log.Write("No hay impresoras instaladas en Windows.");
            }
        }

        // ------------------------------------------------------------------
        // Cargar / guardar configuracion
        // ------------------------------------------------------------------

        private void LoadSettings()
        {
            _posBoxesCombo.SelectedIndex = _config.PosBoxes;
            _autoStartCheck.Checked = _config.Auto;
            _runAtStartupCheck.Checked = IsRunAtStartup();
            _mainRefCheck.Checked = false;
            _saveReceiptsCheck.Checked = false;

            _portBox1.Text = _config.Port1.ToString(CultureInfo.InvariantCulture);
            _portBox2.Text = _config.Port2.ToString(CultureInfo.InvariantCulture);
            _pdfDirBox.Text = _config.PdfOutputDir;

            SelectPrinter(_printerCombo1, _config.Printer1);
            SelectPrinter(_printerCombo2, _config.Printer2);

            ApplyTabState();

            if (_config.Auto)
            {
                if (_config.PosBoxes >= 1)
                {
                    StartServer(1);
                }
                if (_config.PosBoxes >= 2)
                {
                    StartServer(2);
                }
            }
        }

        private void SaveClick(object sender, EventArgs e)
        {
            SaveAll();
        }

        private void LogClick(object sender, EventArgs e)
        {
            OpenLogFile();
        }

        private void BrowsePdfDirClick(object sender, EventArgs e)
        {
            using (FolderBrowserDialog dialog = new FolderBrowserDialog())
            {
                dialog.Description = "Carpeta donde guardar los PDF de prueba";
                dialog.ShowNewFolderButton = true;

                string current = _pdfDirBox.Text.Trim();
                if (current.Length > 0 && Directory.Exists(current))
                {
                    dialog.SelectedPath = current;
                }

                if (dialog.ShowDialog(this) == DialogResult.OK)
                {
                    _pdfDirBox.Text = dialog.SelectedPath;
                }
            }
        }

        private void SaveAll()
        {
            int port1;
            int port2;

            if (!TryReadPort(_portBox1, out port1))
            {
                MessageBox.Show(this, "El puerto del Atlas-Box 1 no es valido (1-65535).",
                    "Atlas-Box", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                _portBox1.Focus();
                return;
            }

            if (!TryReadPort(_portBox2, out port2))
            {
                MessageBox.Show(this, "El puerto del Atlas-Box 2 no es valido (1-65535).",
                    "Atlas-Box", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                _portBox2.Focus();
                return;
            }

            _config.PosBoxes = _posBoxesCombo.SelectedIndex;
            _config.Auto = _autoStartCheck.Checked;
            _config.Printer1 = SelectedPrinter(_printerCombo1);
            _config.Printer2 = SelectedPrinter(_printerCombo2);
            _config.Port1 = port1;
            _config.Port2 = port2;
            _config.PdfOutputDir = _pdfDirBox.Text.Trim();
            _config.Save();

            SetRunAtStartup(_runAtStartupCheck.Checked);
            ApplyTabState();
            UpdateRunningServers();

            Log.Write("Configuracion guardada.");
            SetStatus("Configuracion guardada");
        }

        private void UpdateRunningServers()
        {
            if (_server1 != null)
            {
                _server1.PrinterName = _config.Printer1;
                _server1.FontSize = _config.FontSize;
                _server1.PaperWidthMm = _config.PaperWidthMm;
                _server1.PdfOutputDir = _config.PdfOutputDir;

                if (_server1.Port != _config.Port1)
                {
                    Log.Write("Atlas-Box 1: reinicia el servidor para aplicar el puerto {0}.", _config.Port1);
                }
            }

            if (_server2 != null)
            {
                _server2.PrinterName = _config.Printer2;
                _server2.FontSize = _config.FontSize;
                _server2.PaperWidthMm = _config.PaperWidthMm;
                _server2.PdfOutputDir = _config.PdfOutputDir;

                if (_server2.Port != _config.Port2)
                {
                    Log.Write("Atlas-Box 2: reinicia el servidor para aplicar el puerto {0}.", _config.Port2);
                }
            }
        }

        private static string SelectedPrinter(ComboBox combo)
        {
            if (combo.SelectedIndex <= 0 || combo.SelectedItem == null)
            {
                return "nada";
            }
            return combo.SelectedItem.ToString();
        }

        private static void SelectPrinter(ComboBox combo, string printer)
        {
            if (string.IsNullOrEmpty(printer) || printer.Equals("nada", StringComparison.OrdinalIgnoreCase))
            {
                combo.SelectedIndex = 0;
                return;
            }

            int index = combo.Items.IndexOf(printer);
            combo.SelectedIndex = index >= 0 ? index : 0;
        }

        private static bool TryReadPort(TextBox box, out int port)
        {
            return int.TryParse(box.Text.Trim(), NumberStyles.Integer,
                       CultureInfo.InvariantCulture, out port)
                && port > 0 && port < 65536;
        }

        // ------------------------------------------------------------------
        // Arranque y parada de los servidores
        // ------------------------------------------------------------------

        private void StartClick(object sender, EventArgs e)
        {
            if (sender == _startButton1)
            {
                StartServer(1);
            }
            else if (sender == _startButton2)
            {
                StartServer(2);
            }
        }

        private void StopClick(object sender, EventArgs e)
        {
            if (sender == _stopButton1)
            {
                StopServer(1);
            }
            else if (sender == _stopButton2)
            {
                StopServer(2);
            }
        }

        private void StartServer(int index)
        {
            if (index == 1 && _server1 != null)
            {
                return;
            }
            if (index == 2 && _server2 != null)
            {
                return;
            }
            if (index == 2 && _config.PosBoxes < 2)
            {
                return;
            }

            TextBox portBox = index == 1 ? _portBox1 : _portBox2;
            ComboBox printerCombo = index == 1 ? _printerCombo1 : _printerCombo2;

            int port;
            if (!TryReadPort(portBox, out port))
            {
                MessageBox.Show(this, "El puerto del PosBox " + index + " no es valido (1-65535).",
                    "Atlas-Box", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                portBox.Focus();
                return;
            }

            HwProxyServer server = new HwProxyServer(
                "PosBox " + index,
                port,
                SelectedPrinter(printerCombo),
                _config.FontSize,
                _config.PaperWidthMm,
                _config.PdfOutputDir);

            string error;
            if (!server.Start(out error))
            {
                MessageBox.Show(this, "El puerto " + port + " esta en uso.\n\n" + error,
                    "Atlas-Box", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                SetStatus("No se pudo iniciar el PosBox " + index + ": " + error);
                return;
            }

            if (index == 1)
            {
                _server1 = server;
            }
            else
            {
                _server2 = server;
            }

            UpdateServerUi(index);
            SetStatus("PosBox " + index + " escuchando en el puerto " + port);
        }

        private void StopServer(int index)
        {
            if (index == 1)
            {
                if (_server1 != null)
                {
                    _server1.Stop();
                    _server1 = null;
                }
            }
            else
            {
                if (_server2 != null)
                {
                    _server2.Stop();
                    _server2 = null;
                }
            }

            UpdateServerUi(index);
        }

        private void UpdateServerUi(int index)
        {
            HwProxyServer server = index == 1 ? _server1 : _server2;
            Button startButton = index == 1 ? _startButton1 : _startButton2;
            Button stopButton = index == 1 ? _stopButton1 : _stopButton2;
            Label stateLabel = index == 1 ? _stateLabel1 : _stateLabel2;
            bool tabEnabled = index == 1 ? _config.PosBoxes >= 1 : _config.PosBoxes >= 2;

            if (server != null)
            {
                startButton.Enabled = false;
                stopButton.Enabled = true;
                stateLabel.Text = "Escuchando en el puerto " + server.Port;
                stateLabel.ForeColor = Color.ForestGreen;
            }
            else
            {
                startButton.Enabled = tabEnabled;
                stopButton.Enabled = false;
                stateLabel.Text = "Detenido";
                stateLabel.ForeColor = Color.DimGray;
            }

            UpdateTrayText();
        }

        private void ApplyTabState()
        {
            bool enabled1 = _config.PosBoxes >= 1;
            bool enabled2 = _config.PosBoxes >= 2;

            if (!enabled1 && _server1 != null)
            {
                StopServer(1);
            }
            if (!enabled2 && _server2 != null)
            {
                StopServer(2);
            }

            SetTabContentEnabled(_tabBox1, enabled1);
            SetTabContentEnabled(_tabBox2, enabled2);

            UpdateServerUi(1);
            UpdateServerUi(2);

            if (!enabled1 && _tabs.SelectedIndex == 1)
            {
                _tabs.SelectedIndex = 0;
            }
            if (!enabled2 && _tabs.SelectedIndex == 2)
            {
                _tabs.SelectedIndex = 0;
            }
        }

        private void SetTabContentEnabled(TabPage page, bool enabled)
        {
            foreach (Control control in page.Controls)
            {
                control.Enabled = enabled;
            }
        }

        private void TabsSelecting(object sender, TabControlCancelEventArgs e)
        {
            if (e.TabPageIndex == 1 && _config.PosBoxes < 1)
            {
                e.Cancel = true;
            }
            else if (e.TabPageIndex == 2 && _config.PosBoxes < 2)
            {
                e.Cancel = true;
            }
        }

        // ------------------------------------------------------------------
        // Inicio automatico con Windows
        // ------------------------------------------------------------------

        private static bool IsRunAtStartup()
        {
            try
            {
                using (RegistryKey key = Registry.CurrentUser.OpenSubKey(RunKeyPath, false))
                {
                    if (key == null)
                    {
                        return false;
                    }

                    object value = key.GetValue(RunKeyName);
                    return value != null && value.ToString().Trim().Length > 0;
                }
            }
            catch
            {
                return false;
            }
        }

        private void SetRunAtStartup(bool enabled)
        {
            try
            {
                using (RegistryKey key = Registry.CurrentUser.OpenSubKey(RunKeyPath, true))
                {
                    if (key == null)
                    {
                        return;
                    }

                    if (enabled)
                    {
                        key.SetValue(RunKeyName, "\"" + Application.ExecutablePath + "\"");
                    }
                    else
                    {
                        key.DeleteValue(RunKeyName, false);
                    }
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, "No se pudo cambiar el inicio automatico de Windows:\n" + ex.Message,
                    "Atlas-Box", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
        }

        // ------------------------------------------------------------------
        // Bandeja del sistema
        // ------------------------------------------------------------------

        private void CreateTrayIcon()
        {
            _trayIcon = new NotifyIcon();
            _trayIcon.Icon = SystemIcons.Application;
            _trayIcon.Text = Text;
            _trayIcon.Visible = true;

            ContextMenuStrip menu = new ContextMenuStrip();

            ToolStripMenuItem openItem = new ToolStripMenuItem("Abrir " + Text);
            openItem.Font = new Font(openItem.Font, FontStyle.Bold);
            openItem.Click += TrayOpenClick;
            menu.Items.Add(openItem);
            menu.Items.Add(new ToolStripSeparator());

            ToolStripMenuItem exitItem = new ToolStripMenuItem("Salir");
            exitItem.Click += TrayExitClick;
            menu.Items.Add(exitItem);

            _trayIcon.ContextMenuStrip = menu;
            _trayIcon.DoubleClick += TrayDoubleClick;

            UpdateTrayText();
        }

        private void TrayOpenClick(object sender, EventArgs e)
        {
            ShowFromTray();
        }

        private void TrayDoubleClick(object sender, EventArgs e)
        {
            ShowFromTray();
        }

        private void TrayExitClick(object sender, EventArgs e)
        {
            _reallyExit = true;
            Close();
        }

        public void ShowFromTray()
        {
            if (IsDisposed)
            {
                return;
            }

            ShowInTaskbar = true;

            if (WindowState == FormWindowState.Minimized)
            {
                WindowState = FormWindowState.Normal;
            }

            Show();
            Activate();
            BringToFront();
        }

        private void HideToTray()
        {
            Hide();
            ShowInTaskbar = false;

            if (!_trayHintShown && _trayIcon != null)
            {
                _trayHintShown = true;
                _trayIcon.ShowBalloonTip(3000, Text,
                    "Sigue ejecutandose en la bandeja del sistema. Doble clic para abrir.",
                    ToolTipIcon.Info);
            }
        }

        private void UpdateTrayText()
        {
            if (_trayIcon == null)
            {
                return;
            }

            string text = Text;

            if (_server1 != null)
            {
                text += " | PosBox 1: " + _server1.Port;
            }

            if (_server2 != null)
            {
                text += " | PosBox 2: " + _server2.Port;
            }

            // NotifyIcon.Text admite como maximo 63 caracteres en .NET Framework.
            if (text.Length > 63)
            {
                text = text.Substring(0, 60) + "...";
            }

            _trayIcon.Text = text;
        }

        // ------------------------------------------------------------------
        // Estado y cierre
        // ------------------------------------------------------------------

        private void SetStatus(string text)
        {
            if (string.IsNullOrEmpty(text))
            {
                return;
            }

            string single = text.Replace("\r", " ").Replace("\n", " ");
            if (single.Length > 160)
            {
                single = single.Substring(0, 157) + "...";
            }

            _statusLabel.Text = DateTime.Now.ToString("HH:mm:ss") + "  " + single;
        }

        private void OnLogMessage(string message)
        {
            if (_closing || IsDisposed)
            {
                return;
            }

            try
            {
                if (InvokeRequired)
                {
                    BeginInvoke(new Action<string>(SetStatus), message);
                }
                else
                {
                    SetStatus(message);
                }
            }
            catch (ObjectDisposedException)
            {
            }
            catch (InvalidOperationException)
            {
            }
        }

        private void OpenLogFile()
        {
            try
            {
                string path = Log.FilePath;
                if (!string.IsNullOrEmpty(path))
                {
                    if (!File.Exists(path))
                    {
                        File.WriteAllText(path, "");
                    }

                    System.Diagnostics.Process.Start("notepad.exe", "\"" + path + "\"");
                }
            }
            catch (Exception ex)
            {
                MessageBox.Show(this, "No se pudo abrir el log:\n" + ex.Message,
                    "Atlas-Box", MessageBoxButtons.OK, MessageBoxIcon.Warning);
            }
        }

        private void MainFormClosing(object sender, FormClosingEventArgs e)
        {
            Log.Write("Cierre solicitado ({0}); salir={1}.", e.CloseReason, _reallyExit);

            if (!_reallyExit
                && e.CloseReason != CloseReason.WindowsShutDown
                && e.CloseReason != CloseReason.ApplicationExitCall)
            {
                e.Cancel = true;
                HideToTray();
                return;
            }

            _closing = true;

            if (_trayIcon != null)
            {
                _trayIcon.Visible = false;
            }

            if (_server1 != null)
            {
                _server1.Stop();
                _server1 = null;
            }

            if (_server2 != null)
            {
                _server2.Stop();
                _server2 = null;
            }
        }

        protected override void Dispose(bool disposing)
        {
            if (disposing && _trayIcon != null)
            {
                _trayIcon.Visible = false;
                _trayIcon.Dispose();
                _trayIcon = null;
            }

            base.Dispose(disposing);
        }
    }
}
