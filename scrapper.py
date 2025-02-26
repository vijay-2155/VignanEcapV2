import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup, SoupStrainer
import logging
import time
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def fetch_attendance(page, username, password):
    try:
        # Navigate to login page
        await page.goto("https://webprosindia.com/vignanit/Default.aspx")
        await page.wait_for_load_state("networkidle")

        # Fill login form
        await page.fill("#txtId2", username)
        await page.fill("#txtPwd2", password)

        # Execute JavaScript and submit
        await page.evaluate("encryptJSText(2)")
        await page.evaluate("setValue(2)")
        await page.click("#imgBtn2")
        await page.wait_for_load_state("networkidle", timeout=10000)  # Wait for login response

        # Check for login errors
        error = await page.query_selector("#lblError2")
        if error and await error.inner_text():
            logging.warning(f"Login failed: {await error.inner_text()}")
            return False, "❌ Invalid Username or Password"

        # Verify successful login
        if not await page.query_selector("#divscreens"):
            logging.error("Login failed: #divscreens not found")
            return False, "❌ Authentication Failed"

        return True, "✅ Logged in successfully"

    except Exception as e:
        logging.error(f"Error: {str(e)}")
        return False, f"❌ Error: {str(e)}"

async def get_attendance_data(page):
    """Extract attendance data from portal"""
    try:
        # Navigate to attendance page
        academic_url = "https://webprosindia.com/vignanit/Academics/studentacadamicregister.aspx?scrid=2"
        await page.goto(academic_url)
        await page.wait_for_load_state("networkidle")

        # Extract HTML content
        html = await page.content()
        return html, "Data extracted successfully"

    except Exception as e:
        logging.error(f"Failed to get attendance data: {str(e)}")
        return None, f"Failed to get attendance data: {str(e)}"

def parse_attendance_data(html):
    """Parse attendance HTML and return formatted data"""
    try:
        soup = BeautifulSoup(html, 'lxml', parse_only=SoupStrainer(['tr', 'td']))

        # Get student ID
        student_id = soup.select_one('td.reportData2').text.strip().replace(':', '').strip()

        # Get dates and find today's column
        header_row = soup.select_one('tr.reportHeading2WithBackground')
        dates = [td.text.strip() for td in header_row.select('td')]
        today = time.strftime("%d/%m")
        today_index = next((i for i, date in enumerate(dates) if today in date), None)

        # Process attendance data
        rows = soup.select('tr[title]')
        total_present = total_classes = 0
        todays_attendance = []
        subject_attendance = []

        for row in rows:
            cells = row.select('td.cellBorder')
            if len(cells) >= 2:
                subject = cells[1].text.strip()
                attendance = cells[-2].text.strip()
                percentage = cells[-1].text.strip()

                if attendance != "0/0":
                    present, total = map(int, attendance.split('/'))
                    total_present += present
                    total_classes += total

                    # Process today's status if the column exists
                    if today_index is not None and today_index < len(cells):
                        today_text = cells[today_index].text.strip()  # e.g. "A A A" or "A P"
                        # Get a list of statuses (P or A) from the cell text
                        statuses = [s for s in today_text.split() if s in ['P', 'A']]
                        if statuses:
                            # Join statuses with a space (e.g., "A A A" or "A P")
                            joined_statuses = " ".join(statuses)
                            todays_attendance.append(f"{subject}: {joined_statuses}")

                    if percentage != ".00":
                        subject_attendance.append(f"{subject:.<8} {attendance:<7} {percentage}%")

        # Calculate overall percentage and skippable hours
        overall_percentage = (total_present / total_classes * 100) if total_classes > 0 else 0
        skippable_hours = calculate_skippable_hours(total_present, total_classes)
        required_hours = calculate_required_hours(total_present, total_classes)
        attendance_status = {
            'above_threshold': overall_percentage >= 75,
            'required_hours': required_hours
        }
        
        return {
            'student_id': student_id,
            'total_present': total_present,
            'total_classes': total_classes,
            'overall_percentage': overall_percentage,
            'todays_attendance': todays_attendance,
            'subject_attendance': subject_attendance,
            'skippable_hours': skippable_hours,
            'attendance_status': attendance_status
        }
    except Exception as e:
        raise Exception(f"Failed to parse attendance data: {str(e)}")

def calculate_skippable_hours(present, total):
    """Calculate how many hours can be skipped while maintaining 75%"""
    current = (present / total * 100)
    skippable = 0
    while current >= 75 and total < total + 20:
        skippable += 1
        total += 1
        current = (present / total * 100)
    return skippable

def calculate_required_hours(present, total):
    """Calculate how many hours need to be attended to reach 75%"""
    current = (present / total * 100)
    if current >= 75:
        return 0
    
    required = 0
    while current < 75:
        required += 1
        present += 1
        current = (present / total) * 100
        total += 1
    return required

async def get_attendance_report(username: str, password: str) -> str:
    try:
        browser = None

        logging.info(f"Starting attendance check for user {username}")

        async with async_playwright() as p:
            # Launch browser (headless=True for no GUI)
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Login with retry
            success, message = await fetch_attendance(page, username, password)
            if not success:
                if "Authentication Failed" in message:
                    return json.dumps({"error": "Invalid Username or Password"})
                return json.dumps({"error": message})

            # Get attendance data
            html, message = await get_attendance_data(page)
            logging.info(f"Data extraction: {message}")
            if not html:
                return json.dumps({"error": "Failed to fetch attendance data"})

            # Parse and format data
            data = parse_attendance_data(html)
            logging.info("Data parsed successfully")

            # Format output as JSON
            response = {
                "student_id": data['student_id'],
                "total_present": data['total_present'],
                "total_classes": data['total_classes'],
                "overall_percentage": data['overall_percentage'],
                "todays_attendance": data['todays_attendance'],
                "subject_attendance": data['subject_attendance'],
                "skippable_hours": data['skippable_hours'],
                "attendance_status": data['attendance_status']
            }

            logging.info(f"Report generated: {len(json.dumps(response))} characters")
            return json.dumps(response)

    except Exception as e:
        logging.error(f"Error in attendance report: {str(e)}")
        return json.dumps({"error": str(e)})
    finally:
        if browser:
            await browser.close()

if __name__ == "__main__":
    username = "Replace with your username"
    password = "Replace with your password"
    result = asyncio.run(get_attendance_report(username, password))
    print(result)
