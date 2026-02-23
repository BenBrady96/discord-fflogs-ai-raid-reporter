import os
import re
from discord.ext import commands
from google import genai
from utils.fflogs_client import get_report_data

# Channel IDs — set in your .env file
INPUT_CHANNEL_ID = int(os.getenv('INPUT_CHANNEL_ID', '0'))
OUTPUT_CHANNEL_ID = int(os.getenv('OUTPUT_CHANNEL_ID', '0'))

# Regex to extract report codes from FFLogs URLs
FFLOGS_PATTERN = re.compile(r'fflogs\.com/reports/([A-Za-z0-9]+)')


class RaidReporter(commands.Cog):
    """
    Discord cog that generates AI-powered raid performance reports.

    When an FFLogs link is posted in the input channel, this cog:
    1. Extracts the report code from the URL
    2. Queries the FFLogs GraphQL API for fight data
    3. Sends the structured data to Google Gemini for analysis
    4. Posts a formatted report in the output channel
    """

    def __init__(self, bot):
        self.bot = bot
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("WARNING: GEMINI_API_KEY not found in environment variables.")
        self.client = genai.Client(api_key=api_key)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Listen for FFLogs links in the input channel."""
        if message.author == self.bot.user:
            return

        if message.channel.id != INPUT_CHANNEL_ID:
            return

        # Check embeds for FFLogs URLs (webhooks use embeds)
        found_code = None
        if message.embeds:
            for embed in message.embeds:
                if embed.url:
                    match = FFLOGS_PATTERN.search(embed.url)
                    if match:
                        found_code = match.group(1)
                        break

        # Fallback: check message content for plain links
        if not found_code:
            match = FFLOGS_PATTERN.search(message.content)
            if match:
                found_code = match.group(1)

        if found_code:
            print(f"[RaidReporter] Detected report code: {found_code}", flush=True)
            output_channel = self.bot.get_channel(OUTPUT_CHANNEL_ID) or message.channel
            await self.process_report(output_channel, found_code)

    async def process_report(self, channel, report_code):
        """Query FFLogs API, analyse with Gemini, and post the report."""
        async with channel.typing():
            try:
                # Fetch structured fight data from FFLogs API
                print("[RaidReporter] Querying FFLogs API...", flush=True)
                report_data = get_report_data(report_code)

                if not report_data or len(report_data) < 50:
                    await channel.send("⚠️ Could not retrieve meaningful data from this report.")
                    return

                # Analyse with Gemini AI
                print("[RaidReporter] Sending to Gemini for analysis...", flush=True)
                report = await self.generate_report(report_data)

                # Post the report
                link = f"https://www.fflogs.com/reports/{report_code}"
                await channel.send(f"## 📊 Raid Report\n🔗 {link}")
                await self.send_long_message(channel, report)

            except Exception as e:
                print(f"[RaidReporter] Error: {e}", flush=True)
                await channel.send(f"❌ Error generating report: {e}")

    async def generate_report(self, report_data):
        """Send structured fight data to Gemini and generate a formatted report."""
        try:
            prompt = f"""
            You are an expert Final Fantasy XIV Raid Analyst.
            Analyse the following structured data from an FFLogs raid report.
            
            {report_data}

            Please provide a DETAILED Raid Report including:
            1. **Summary of Performance**: Overall how did the team do?
            2. **Key Statistics**: Damage, Healing, Deaths, or any visible patterns.
            3. **Mechanics**: Any obvious issues based on wipes, death counts, and fight percentages.
            4. **Recommendations**: Short advice for improvement.

            Strictly keep it on team performance and not individual performance.
            No player names should appear in the output.
            Format the response in Discord Markdown (use bolding, bullet points, etc.).
            Keep the tone professional but encouraging (like a raid leader).
            """

            response = await self.client.aio.models.generate_content(
                model="models/gemini-2.5-flash",
                contents=prompt
            )
            return response.text
        except Exception as e:
            return f"Gemini API Error: {e}"

    async def send_long_message(self, channel, message):
        """Split and send messages at line boundaries to preserve markdown formatting."""
        if len(message) <= 2000:
            await channel.send(message)
            return

        lines = message.split("\n")
        chunk = ""
        for line in lines:
            # If adding this line would exceed the limit, send the current chunk first
            if len(chunk) + len(line) + 1 > 1900:
                if chunk:
                    await channel.send(chunk)
                chunk = line
            else:
                chunk = f"{chunk}\n{line}" if chunk else line

        if chunk:
            await channel.send(chunk)


async def setup(bot):
    await bot.add_cog(RaidReporter(bot))
