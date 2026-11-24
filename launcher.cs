using System;
using System.Diagnostics;
using System.IO;
using System.Runtime.InteropServices;
using System.Windows.Forms;

internal static class Program
{
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern bool SetDllDirectory(string lpPathName);

    [DllImport("python311.dll", CallingConvention = CallingConvention.Cdecl, CharSet = CharSet.Unicode)]
    private static extern int Py_Main(int argc, string[] argv);

    [STAThread]
    private static int Main(string[] args)
    {
        string baseDir = AppDomain.CurrentDomain.BaseDirectory;
        string appScript = Path.Combine(baseDir, "app.py");
        string rtDir = Path.Combine(baseDir, "runtime");
        string rtDll = Path.Combine(rtDir, "python311.dll");
        string rtPy = Path.Combine(rtDir, "python.exe");

        if (!File.Exists(appScript))
        {
            MessageBox.Show("app.py not found in " + baseDir, "QuickOCR", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }

        // Primary path: host Python 3.11 embeddable in-process so Windows Taskbar uses QuickOCR.exe's icon
        if (File.Exists(rtDll) && File.Exists(rtPy))
        {
            Environment.CurrentDirectory = baseDir;
            SetDllDirectory(rtDir);
            string[] pyArgs = new string[args.Length + 2];
            pyArgs[0] = rtPy;
            pyArgs[1] = appScript;
            for (int i = 0; i < args.Length; i++) pyArgs[i + 2] = args[i];
            return Py_Main(pyArgs.Length, pyArgs);
        }

        // Fallback path: .venv pythonw.exe
        string pythonw = Path.Combine(baseDir, ".venv", "Scripts", "pythonw.exe");
        if (!File.Exists(pythonw))
        {
            MessageBox.Show(
                "Environment not initialized. Please run Setup.bat first.",
                "QuickOCR",
                MessageBoxButtons.OK,
                MessageBoxIcon.Information
            );
            return 1;
        }

        string forwarded = args.Length > 0 ? " " + string.Join(" ", args) : "";
        Process.Start(new ProcessStartInfo
        {
            FileName = pythonw,
            Arguments = "\"" + appScript + "\"" + forwarded,
            WorkingDirectory = baseDir,
            UseShellExecute = false,
            CreateNoWindow = true,
        });
        return 0;
    }
}
