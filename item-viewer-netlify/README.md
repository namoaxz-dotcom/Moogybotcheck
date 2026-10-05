# Item Viewer - Netlify Deployment Edition

โปรเจกต์เวอร์ชันปรับปรุงเพื่อใช้งานบน **Netlify Functions** ร่วมกับ **Turso DB (Cloud SQLite)**

## การปรับเปลี่ยนจากเวอร์ชันเดิม:
1. **Netlify Functions + Express:** แปลง Express app ให้ทำงานบน Serverless Environment ผ่าน `serverless-http`
2. **Cloud Database (Turso):** เปลี่ยนจาก SQLite แบบไฟล์ดิสก์ท้องถิ่น มาใช้ Turso DB (SQLite บน คลาวด์) ซึ่งฟรีและเสถียร
3. **JWT Cookie Authentication:** เปลี่ยนระบบ Session มาเป็น JWT HttpOnly Cookie เพื่อให้ทำงานบน Serverless ไร้สเตตได้สมบูรณ์แบบ
4. **In-Memory File Parsing:** อัปโหลดไฟล์ `.sql` และอ่านค่าจากแรมโดยตรง โดยไม่จำเป็นต้องบันทึกลงไฟล์ดิสก์

---

## ขั้นตอนการ Deploy ลง Netlify

### 1. สมัครใช้งาน Turso DB (ฐานข้อมูลฟรี)
1. ไปที่เว็บไซต์ [https://turso.tech](https://turso.tech) สมัครบัญชีฟรี
2. สร้าง Database ใหม่ (ผ่าน CLI หรือ Dashboard):
   ```bash
   turso db create item-db
   ```
3. ดึง **Database URL**:
   ```bash
   turso db show item-db
   # จะได้ URL รูปแบบ libsql://item-db-yourusername.turso.io
   ```
4. สร้าง **Auth Token**:
   ```bash
   turso db tokens create item-db
   ```

---

### 2. นำโปรเจกต์ขึ้น Netlify
1. นำโฟลเดอร์โปรเจกต์นี้อัปโหลดขึ้น **GitHub** / **GitLab**
2. ไปที่ [Netlify Dashboard](https://app.netlify.com/) แล้วกด **Add new site** > **Import an existing project**
3. เลือก Repository ที่เพิ่งอัปโหลด
4. ในหน้า **Site settings > Environment variables** ตั้งค่าตัวแปรดังนี้:
   - `TURSO_DATABASE_URL` = (ค่า URL จากข้อ 1)
   - `TURSO_AUTH_TOKEN` = (ค่า Token จากข้อ 1)
   - `JWT_SECRET` = (กำหนดรหัสสุ่มสำหรับเข้ารหัส Token เช่น `my-secret-1234`)
5. กด **Deploy Site**

---

## ข้อมูลเข้าสู่ระบบเริ่มต้น
- **Username:** `admin`
- **Password:** `adminpassword`
