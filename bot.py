import discord
from discord.ext import commands
import datetime
import json
import os
import glob
import csv
import io

# ==========================================
# 0. ตั้งค่าพื้นฐาน (เปิด Intents)
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True 
bot = commands.Bot(command_prefix="!", intents=intents)

# ==========================================
# 1. ระบบจัดการไฟล์
# ==========================================
CONFIG_FILE = "config.json"

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

config = load_config()

def save_attendance(user_id, name, type):
    today = datetime.date.today().isoformat()
    file_path = f"attendance_{today}.json"
    data = {}
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    
    uid = str(user_id)
    now_dt = datetime.datetime.now()
    now_time_str = now_dt.strftime("%H:%M:%S")
    
    if uid not in data:
        data[uid] = {"name": name, "check_in": "-", "check_out": "-", "work_seconds": 0, "work_hours_str": "-"}
    
    if type == "in":
        data[uid]["check_in"] = now_time_str
        data[uid]["check_out"] = "-"
        data[uid]["work_hours_str"] = "กำลังจับเวลา..."
    else:
        data[uid]["check_out"] = now_time_str
        if data[uid]["check_in"] != "-":
            in_time = datetime.datetime.strptime(data[uid]["check_in"], "%H:%M:%S")
            out_time = datetime.datetime.strptime(now_time_str, "%H:%M:%S")
            diff = out_time - in_time
            data[uid]["work_seconds"] = data[uid].get("work_seconds", 0) + diff.seconds 
            hours, remainder = divmod(data[uid]["work_seconds"], 3600)
            minutes, _ = divmod(remainder, 60)
            data[uid]["work_hours_str"] = f"{hours}h {minutes}m"
        
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    return data

# ==========================================
# 2. ระบบลงเวลา (เพิ่มวันที่และเวลา)
# ==========================================
class AttendanceView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="ลงเวลาเข้างาน", style=discord.ButtonStyle.success, emoji="✅", custom_id="checkin_btn")
    async def checkin(self, interaction: discord.Interaction, button: discord.ui.Button):
        save_attendance(interaction.user.id, interaction.user.display_name, "in")
        
        ch_id = config.get("daily_channel")
        if ch_id:
            ch = interaction.guild.get_channel(ch_id)
            # 🔥 ดึงข้อมูล วัน/เดือน/ปี และ เวลา
            now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            embed = discord.Embed(
                description=f"☀️ {interaction.user.mention} เข้างานแล้วเมื่อ: `{now_str}`", 
                color=0xCC0000 # แถบสีแดง
            )
            await ch.send(embed=embed)

        await interaction.response.send_message("✅ บันทึกเวลาเข้างานเรียบร้อย!", ephemeral=True)

    @discord.ui.button(label="ลงเวลาออกงาน", style=discord.ButtonStyle.danger, emoji="🚪", custom_id="checkout_btn")
    async def checkout(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = save_attendance(interaction.user.id, interaction.user.display_name, "out")
        
        ch_id = config.get("daily_channel")
        if ch_id:
            ch = interaction.guild.get_channel(ch_id)
            # 🔥 ดึงข้อมูล วัน/เดือน/ปี และ เวลา
            now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            work_hours = data[str(interaction.user.id)]["work_hours_str"]
            
            embed = discord.Embed(
                description=f"🌙 {interaction.user.mention} ออกงานแล้วเมื่อ: `{now_str}`\n⏱️ เวลาทำงานวันนี้: `{work_hours}`", 
                color=0xCC0000 # แถบแดง
            )
            await ch.send(embed=embed)

        await interaction.response.send_message("✅ บันทึกเวลาออกงานเรียบร้อย!", ephemeral=True)

# ==========================================
# 3. ระบบแจ้งลา (Leave System)
# ==========================================
class LeaveApprovalView(discord.ui.View):
    def __init__(self, requester_id):
        super().__init__(timeout=None)
        self.requester_id = requester_id

    @discord.ui.button(label="อนุมัติ", style=discord.ButtonStyle.success, emoji="✅")
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = await bot.fetch_user(self.requester_id)
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.green()
        embed.title = "✅ การลาได้รับการอนุมัติ"
        await interaction.message.edit(embed=embed, view=None)
        try: await user.send(f"✨ แจ้งผล: แอดมิน **อนุมัติ** การลาของคุณเรียบร้อยแล้ว!")
        except: pass
        await interaction.response.send_message("อนุมัติสำเร็จ", ephemeral=True)

    @discord.ui.button(label="ปฏิเสธ", style=discord.ButtonStyle.danger, emoji="❌")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        user = await bot.fetch_user(self.requester_id)
        embed = interaction.message.embeds[0]
        embed.color = discord.Color.red()
        embed.title = "❌ การลาถูกปฏิเสธ"
        await interaction.message.edit(embed=embed, view=None)
        try: await user.send(f"⚠️ แจ้งผล: แอดมิน **ไม่อนุมัติ** การลาของคุณ โปรดติดต่อแอดมินเพิ่มเติม")
        except: pass
        await interaction.response.send_message("ปฏิเสธสำเร็จ", ephemeral=True)

class LeaveModal(discord.ui.Modal, title='📝 แบบฟอร์มแจ้งลา'):
    date = discord.ui.TextInput(label='วันที่ลา', placeholder='เช่น 05/04/2026', required=True)
    reason = discord.ui.TextInput(label='สาเหตุการลา', style=discord.TextStyle.paragraph, required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        ch_id = config.get("admin_backoffice_channel")
        if not ch_id: return await interaction.response.send_message("❌ แอดมินยังไม่ได้ตั้งค่าห้องรับใบลา", ephemeral=True)
        ch = interaction.guild.get_channel(ch_id)
        
        embed = discord.Embed(title="🔔 มีคำขอแจ้งลาใหม่", color=discord.Color.orange())
        embed.add_field(name="👤 ผู้แจ้ง", value=interaction.user.mention)
        embed.add_field(name="📅 วันที่", value=self.date.value)
        embed.add_field(name="📝 สาเหตุ", value=self.reason.value)
        
        await ch.send(embed=embed, view=LeaveApprovalView(interaction.user.id))
        await interaction.response.send_message("✅ ส่งใบลาให้แอดมินตรวจสอบแล้ว กรุณารอรับผลทาง DM ครับ", ephemeral=True)

class LeaveUserView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="กดแจ้งลาที่นี่", style=discord.ButtonStyle.danger, emoji="📝", custom_id="leave_user_btn")
    async def leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(LeaveModal())

# ==========================================
# 4. ระบบประกาศส่วนตัว (DM) สำหรับแอดมิน
# ==========================================
class MassMeetingModal(discord.ui.Modal, title='📢 แจ้งประชุมถึงทุกคน'):
    topic = discord.ui.TextInput(label='หัวข้อการประชุม', required=True)
    detail = discord.ui.TextInput(label='รายละเอียด / เวลา', style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("⏳ กำลังส่งข้อความหาทุกคนในเซิร์ฟเวอร์...", ephemeral=True)
        count = 0
        embed = discord.Embed(title=f"📢 {self.topic.value}", description=self.detail.value, color=discord.Color.purple())
        embed.set_footer(text=f"ส่งโดย: {interaction.user.display_name}")
        for member in interaction.guild.members:
            if not member.bot:
                try:
                    await member.send(embed=embed)
                    count += 1
                except: pass
        await interaction.followup.send(f"✅ ส่ง DM ประชุมให้พนักงานเรียบร้อย! ({count} คน)", ephemeral=True)

class SingleDMModal(discord.ui.Modal, title='🏃 ตามตัวพนักงานด่วน'):
    target_id = discord.ui.TextInput(label='User ID ของพนักงาน', required=True)
    detail = discord.ui.TextInput(label='ข้อความ / สาเหตุ', style=discord.TextStyle.paragraph)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            target_user = await bot.fetch_user(int(self.target_id.value))
            embed = discord.Embed(title="🏃 แอดมินเรียกพบด่วน!", description=self.detail.value, color=discord.Color.red())
            await target_user.send(embed=embed)
            await interaction.response.send_message(f"✅ ส่งข้อความให้ {target_user.name} สำเร็จ!", ephemeral=True)
        except:
            await interaction.response.send_message(f"❌ ส่งไม่สำเร็จ! ตรวจสอบ User ID", ephemeral=True)

class AdminActionView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)

    @discord.ui.button(label="📢 ประกาศประชุม (ทุกคน)", style=discord.ButtonStyle.primary, custom_id="action_meeting")
    async def meeting(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(MassMeetingModal())

    @discord.ui.button(label="🏃 ตามตัวรายบุคคล", style=discord.ButtonStyle.secondary, custom_id="action_follow")
    async def follow(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SingleDMModal())

# ==========================================
# 5. แผงควบคุมตั้งค่า (Admin Panel)
# ==========================================
class ChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, placeholder, key):
        super().__init__(placeholder=placeholder, channel_types=[discord.ChannelType.text], custom_id=f"sel_{key}")
        self.key = key
    async def callback(self, interaction: discord.Interaction):
        config[self.key] = self.values[0].id
        save_config(config)
        await interaction.response.send_message(f"ตั้งค่า {self.placeholder} สำเร็จ!", ephemeral=True)

class SetupView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ChannelSelect("1. ห้องปุ่มเช็คชื่อ", "checkin_channel"))
        self.add_item(ChannelSelect("2. ห้องปุ่มแจ้งลา", "leave_channel"))
        self.add_item(ChannelSelect("3. ห้องแผงแอดมิน (ประชุม/ตามตัว)", "admin_action_channel"))
        self.add_item(ChannelSelect("4. ห้องอัปเดตเวลาสดๆ (กระดานสรุป)", "daily_channel"))
        self.add_item(ChannelSelect("5. ห้องหลังบ้าน (รับใบลา/เดือน/Excel)", "admin_backoffice_channel"))

class MainAdminPanel(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    
    @discord.ui.button(label="⚙️ ตั้งค่าห้องต่างๆ (Setup)", style=discord.ButtonStyle.secondary, custom_id="btn_setup", row=0)
    async def setup(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("เลือกห้องตามการใช้งานด้านล่าง:", view=SetupView(), ephemeral=True)

    @discord.ui.button(label="⏰ เพิ่มปุ่มเช็คชื่อลงห้อง", style=discord.ButtonStyle.success, custom_id="btn_dep_att", row=1)
    async def deploy_att(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = interaction.guild.get_channel(config.get("checkin_channel"))
        await ch.send(embed=discord.Embed(title="⏱️ ลงเวลาทำงาน", color=0x42f554), view=AttendanceView())
        await interaction.response.send_message("🚀 ส่งแผงเช็คชื่อแล้ว", ephemeral=True)

    @discord.ui.button(label="📝 เพิ่มปุ่มแจ้งลาลงห้อง", style=discord.ButtonStyle.danger, custom_id="btn_dep_leave", row=1)
    async def deploy_leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = interaction.guild.get_channel(config.get("leave_channel"))
        await ch.send(embed=discord.Embed(title="🏥 แจ้งลางาน", color=0xf54242), view=LeaveUserView())
        await interaction.response.send_message("🚀 ส่งแผงแจ้งลาแล้ว", ephemeral=True)

    @discord.ui.button(label="🛠️ เพิ่มปุ่มแอดมิน (ประชุม) ลงห้อง", style=discord.ButtonStyle.primary, custom_id="btn_dep_act", row=1)
    async def deploy_actions(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = interaction.guild.get_channel(config.get("admin_action_channel"))
        await ch.send(embed=discord.Embed(title="🛠️ เครื่องมือแอดมิน", description="แจ้งเตือนและตามตัว"), view=AdminActionView())
        await interaction.response.send_message("🚀 ส่งเครื่องมือแอดมินแล้ว", ephemeral=True)

    @discord.ui.button(label="🗓️ สรุปรายเดือน", style=discord.ButtonStyle.secondary, emoji="📊", custom_id="btn_monthly", row=2)
    async def monthly(self, interaction: discord.Interaction, button: discord.ui.Button):
        ch = interaction.guild.get_channel(config.get("admin_backoffice_channel"))
        now = datetime.datetime.now()
        files = glob.glob(f"attendance_{now.strftime('%Y-%m')}-*.json")
        summary = {}
        for file in files:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for uid, info in data.items():
                    if uid not in summary: summary[uid] = {"name": info["name"], "days": 0}
                    if info["check_in"] != "-": summary[uid]["days"] += 1
        
        embed = discord.Embed(title=f"📊 สรุปจำนวนวันทำงานเดือน {now.strftime('%m/%Y')}", color=0xFFD700)
        desc = "".join([f"👤 <@{uid}>: ทำงาน **{s['days']}** วัน\n" for uid, s in summary.items()])
        embed.description = desc if desc else "ไม่มีข้อมูล"
        await ch.send(embed=embed)
        await interaction.response.send_message("✅ ส่งรายงานไปที่ห้องหลังบ้านแล้ว", ephemeral=True)

    @discord.ui.button(label="📥 โหลด Excel (CSV)", style=discord.ButtonStyle.success, emoji="📥", custom_id="btn_excel", row=2)
    async def export_excel(self, interaction: discord.Interaction, button: discord.ui.Button):
        now = datetime.datetime.now()
        files = glob.glob(f"attendance_{now.strftime('%Y-%m')}-*.json")
        summary = {}
        for file in files:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
                for uid, info in data.items():
                    if uid not in summary: summary[uid] = {"name": info["name"], "days": 0, "total_sec": 0}
                    if info["check_in"] != "-": summary[uid]["days"] += 1
                    summary[uid]["total_sec"] += info.get("work_seconds", 0)

        output = io.StringIO()
        output.write('\ufeff') # กันฟอนต์ไทยเพี้ยน
        writer = csv.writer(output)
        writer.writerow(["User ID", "Name", "Days Present", "Total Work Hours"])
        
        for uid, s in summary.items():
            hours, remainder = divmod(s["total_sec"], 3600)
            minutes, _ = divmod(remainder, 60)
            writer.writerow([uid, s["name"], s["days"], f"{hours}h {minutes}m"])
        
        output.seek(0)
        file = discord.File(fp=io.BytesIO(output.getvalue().encode('utf-8')), filename=f"Report_{now.strftime('%B_%Y')}.csv")
        
        ch = interaction.guild.get_channel(config.get("admin_backoffice_channel"))
        await ch.send(content=f"📊 ไฟล์ Excel รายงานประจำเดือน {now.strftime('%m/%Y')}", file=file)
        await interaction.response.send_message("✅ ส่งไฟล์ Excel ไปที่ห้องหลังบ้านแล้วครับ", ephemeral=True)

# ==========================================
# 6. รันบอทและลงทะเบียนปุ่ม
# ==========================================
@bot.command()
@commands.has_permissions(administrator=True)
async def admin(ctx):
    await ctx.send(embed=discord.Embed(title="🎛️ Moggy Setup", color=0xC8A0FF), view=MainAdminPanel())

@bot.event
async def on_ready():
    print(f'✅ Logged in as {bot.user}')
    bot.add_view(MainAdminPanel())
    bot.add_view(AttendanceView())
    bot.add_view(AdminActionView())
    bot.add_view(LeaveUserView())

# 🔥 อย่าลืมใส่ Token ของบอทตัวเองที่นี่!
token = os.environ.get("BOT_TOKEN")
bot.run(token)