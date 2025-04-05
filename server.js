console.log("\x1b[33m%s\x1b[0m", "⚠️  IMPORTANT: This is a Python project, not a Node.js project!");
console.log("\x1b[36m%s\x1b[0m", "✅ Steps to run this server:");
console.log("\x1b[37m%s\x1b[0m", "1. Make sure Python is installed (https://www.python.org/downloads/)");
console.log("\x1b[37m%s\x1b[0m", "2. Install required packages: python -m pip install -r requirements.txt");
console.log("\x1b[37m%s\x1b[0m", "3. Set your OpenAI API key in the .env file");
console.log("\x1b[37m%s\x1b[0m", "4. Run the server: python web_server.py");
console.log("\n\x1b[36m%s\x1b[0m", "📝 NOTE: You need a valid OpenAI API key in the .env file");
console.log("\x1b[36m%s\x1b[0m", "   Edit the .env file and replace 'your_openai_api_key_here' with your actual API key");
console.log("\n\x1b[32m%s\x1b[0m", "Attempting to run the Python server for you...");

try {
  const { spawn } = require('child_process');
  
  // Try to execute with 'python' command first
  console.log("\x1b[33m%s\x1b[0m", "Trying with 'python' command...");
  const pythonProcess = spawn('python', ['web_server.py']);

  pythonProcess.stdout.on('data', (data) => {
    console.log(`${data}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`${data}`);
  });

  pythonProcess.on('error', (err) => {
    // If python command fails, try with python3
    console.log("\x1b[33m%s\x1b[0m", "Python command not found, trying with 'python3' command...");
    const python3Process = spawn('python3', ['web_server.py']);
    
    python3Process.stdout.on('data', (data) => {
      console.log(`${data}`);
    });
    
    python3Process.stderr.on('data', (data) => {
      console.error(`${data}`);
    });
    
    python3Process.on('error', (err) => {
      console.error("\x1b[31m%s\x1b[0m", "❌ ERROR: Could not start Python. Please make sure Python is installed and run the command manually:");
      console.log("\x1b[37m%s\x1b[0m", "python web_server.py");
    });
  });

  pythonProcess.on('close', (code) => {
    if (code !== 0) {
      console.log(`\x1b[31m%s\x1b[0m`, `❌ Python process exited with code ${code}`);
      console.log("\x1b[37m%s\x1b[0m", "Check the error message above. You may need to:");
      console.log("\x1b[37m%s\x1b[0m", "1. Install required packages: python -m pip install -r requirements.txt");
      console.log("\x1b[37m%s\x1b[0m", "2. Set your OpenAI API key in the .env file");
    } else {
      console.log(`\x1b[32m%s\x1b[0m`, `✅ Python process completed successfully!`);
    }
  });
} catch (err) {
  console.error("\x1b[31m%s\x1b[0m", `❌ ERROR: ${err.message}`);
  console.log("\x1b[37m%s\x1b[0m", "Please run the server manually with: python web_server.py");
}
