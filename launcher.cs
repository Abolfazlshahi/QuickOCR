using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class Program
{
    [STAThread]
    private static void Main(string[] args)
    {
        string baseDir = AppDomain.CurrentDomain.BaseDirectory;
        string pythonw = Path.Combine(baseDir, ".venv", "Scripts", "pythonw.exe");
        string appScript = Path.Combine(baseDir, "app.py");

        if (!File.Exists(pythonw) || !File.Exists(appScript))
        {
            MessageBox.Show(
                "Environment not initialized. Please run Setup.bat first.",
                "QuickOCR",
                MessageBoxButtons.OK,
                MessageBoxIcon.Information
            );
            return;
        }

        string forwarded = args.Length > 0 ? " " + string.Join(" ", args) : "";
        var psi = new ProcessStartInfo
        {
            FileName = pythonw,
            Arguments = "\"" + appScript + "\"" + forwarded,
            WorkingDirectory = baseDir,
            UseShellExecute = false,
            CreateNoWindow = true,
        };
        Process.Start(psi);
    }
}
