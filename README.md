# VignanEcap Attendance Bot 🤖

A FastAPI-based Telegram bot that provides real-time attendance tracking for Vignan University students, leveraging async architecture and Playwright for web automation.

## Features ✨

- **Real-time Attendance Tracking**: Instant access to attendance information
- **Async Processing**: Handles multiple requests concurrently
- **Multiple Login Methods**:
  - Quick Access with custom keywords
  - One-time credential check
  - Secure credential storage
- **Subject-wise Breakdown**: Detailed attendance for each subject
- **Smart Calculations**:
  - Required hours to reach 75%
  - Skippable classes while maintaining attendance
- **Secure Operations**:
  - Encrypted credential storage
  - Personal keyword system
  - Secure session management

## Tech Stack 🛠️

- **Backend Framework**: FastAPI
- **Web Automation**: Playwright
- **Bot Framework**: python-telegram-bot
- **Database**: SQLite
- **Deployment**: AWS EC2 (Ubuntu)
- **Process Management**: Systemd
- **Language**: Python 3.11+

## Installation 📦

```bash
# Clone the repository
git clone https://github.com/vijay-2155/VignanEcapV2.git
cd VignanEcap2

# Create virtual environment
python3 -m venv venv
# linux based
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium
```

## Configuration ⚙️

```python
# Configure your environment variables
TELEGRAM_TOKEN="your_telegram_bot_token"
```

## Deployment 🚀

### Local Development

```bash
# Start the FastAPI application
uvicorn app:app_api --host 0.0.0.0 --port 5000 --reload
```

### AWS EC2 Deployment

```bash
# Set up systemd service
sudo nano /etc/systemd/system/attendance-bot.service

# Enable and start service
sudo systemctl enable attendance-bot
sudo systemctl start attendance-bot

# Monitor logs
sudo journalctl -u attendance-bot -f
```

## Usage 📱

1. Start the bot: [@VignanEcapbot](https://t.me/VignanEcapbot)
2. Commands:
   - `/start` - Introduction to bot
   - `/set username password keyword` - Save credentials
   - `/check username password` - One-time check

## Architecture 🏗️

### Async Implementation
```python
# Request Queue System
request_queue = asyncio.Queue()

# Async Queue Processing
async def process_queue():
    while True:
        username, password, future = await request_queue.get()
        try:
            report = await get_attendance_report(username, password)
            future.set_result(json.dumps(report))
        except Exception as e:
            future.set_exception(e)
```

### Key Components
- FastAPI for async HTTP handling
- Playwright for async web automation
- AsyncIO queue for request management
- Systemd for process management
- SQLite for data persistence

## License 📄

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments 🙏
Special thanks to my seniors and teachers for their valuable guidance on:
- Implementing async architecture with FastAPI
- Migrating from Selenium to Playwright
- AWS deployment best practices

## Contact 📫

Your Name - vijay kumar tholeti 

Project Link: https://github.com/vijay-2155/VignanEcapV2

## Screenshots 📸
## Start and set up of account for quick access:
![Screenshot 2025-03-01 233556](https://github.com/user-attachments/assets/91f19676-cdcb-4e7a-bb95-2bea254716ee)


## Report generated using keyword:
![Screenshot 2025-03-01 233956](https://github.com/user-attachments/assets/1b46ca89-7c0c-458c-84d9-59c8b49aff35)

## one time check:
![Screenshot 2025-03-01 233910](https://github.com/user-attachments/assets/2f7b46fd-5021-4410-a3e3-0a808090107c)



