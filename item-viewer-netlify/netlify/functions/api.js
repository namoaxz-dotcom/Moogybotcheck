const express = require('express');
const serverless = require('serverless-http');
const cookieParser = require('cookie-parser');
const jwt = require('jsonwebtoken');
const multer = require('multer');
const path = require('path');
const { createClient } = require('@libsql/client');
const bcrypt = require('bcryptjs');

const app = express();
const upload = multer({ storage: multer.memoryStorage() });

// ตั้งค่า Path ของ views ให้ทำงานได้ถูกต้องบน Netlify Functions
app.set('views', path.join(process.cwd(), 'views'));
app.set('view engine', 'ejs');

app.use(express.urlencoded({ extended: true }));
app.use(express.json());
app.use(cookieParser());

// เชื่อมต่อฐานข้อมูล Turso (Cloud SQLite)
const dbUrl = process.env.TURSO_DATABASE_URL;
const authToken = process.env.TURSO_AUTH_TOKEN;

const db = createClient({
  url: dbUrl || 'file:local.db',
  authToken: authToken
});

// Middleware สร้างตารางและ Admin เริ่มต้นถ้ายกขึ้นครั้งแรก
let dbInitialized = false;
async function initDb() {
  if (dbInitialized) return;
  
  await db.execute(`
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      password TEXT NOT NULL,
      role TEXT CHECK(role IN ('admin', 'user')) NOT NULL
    );
  `);
  
  await db.execute(`
    CREATE TABLE IF NOT EXISTS items (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      label TEXT NOT NULL
    );
  `);

  const adminCheck = await db.execute({
    sql: 'SELECT * FROM users WHERE username = ?',
    args: ['admin']
  });

  if (adminCheck.rows.length === 0) {
    const hashedPassword = bcrypt.hashSync('adminpassword', 10);
    await db.execute({
      sql: 'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
      args: ['admin', hashedPassword, 'admin']
    });
  }

  dbInitialized = true;
}

app.use(async (req, res, next) => {
  try {
    await initDb();
    next();
  } catch (err) {
    console.error('DB init error:', err);
    next(err);
  }
});

const JWT_SECRET = process.env.JWT_SECRET || 'secret-key-item-viewer-netlify';

function getUserFromToken(req) {
  const token = req.cookies.token;
  if (!token) return null;
  try {
    return jwt.verify(token, JWT_SECRET);
  } catch (err) {
    return null;
  }
}

function requireLogin(req, res, next) {
  const user = getUserFromToken(req);
  if (!user) return res.redirect('/login');
  req.user = user;
  next();
}

function requireAdmin(req, res, next) {
  const user = getUserFromToken(req);
  if (!user || user.role !== 'admin') {
    return res.status(403).send('Access Denied: Admin privileges required.');
  }
  req.user = user;
  next();
}

app.get('/', (req, res) => res.redirect('/items'));

app.get('/login', (req, res) => res.render('login', { error: null }));

app.post('/login', async (req, res) => {
  const { username, password } = req.body;
  try {
    const result = await db.execute({
      sql: 'SELECT * FROM users WHERE username = ?',
      args: [username]
    });
    const user = result.rows[0];
    if (user && bcrypt.compareSync(password, user.password)) {
      const token = jwt.sign(
        { id: user.id, username: user.username, role: user.role },
        JWT_SECRET,
        { expiresIn: '1d' }
      );
      res.cookie('token', token, { httpOnly: true, maxAge: 86400000 });
      return res.redirect('/items');
    }
    res.render('login', { error: 'Username หรือ Password ไม่ถูกต้อง' });
  } catch (err) {
    console.error(err);
    res.render('login', { error: 'เกิดข้อผิดพลาดในการเข้าสู่ระบบ' });
  }
});

app.get('/logout', (req, res) => {
  res.clearCookie('token');
  res.redirect('/login');
});

app.get('/items', requireLogin, async (req, res) => {
  const search = req.query.search || '';
  let items = [];
  try {
    if (search) {
      const result = await db.execute({
        sql: 'SELECT * FROM items WHERE name LIKE ? OR label LIKE ? LIMIT 500',
        args: [`%${search}%`, `%${search}%`]
      });
      items = result.rows;
    } else {
      const result = await db.execute('SELECT * FROM items LIMIT 500');
      items = result.rows;
    }
  } catch (err) {
    console.error(err);
  }
  res.render('items', { user: req.user, items, search });
});

app.get('/admin/upload', requireAdmin, (req, res) => {
  res.render('admin_upload', { user: req.user, message: null });
});

app.post('/admin/upload', requireAdmin, upload.single('sqlfile'), async (req, res) => {
  if (!req.file) return res.render('admin_upload', { user: req.user, message: 'กรุณาเลือกไฟล์ SQL' });

  const content = req.file.buffer.toString('utf8');
  const regex = /\('([^']+)',\s*'([^']+)'/g;
  let match;
  const itemsToAdd = [];

  while ((match = regex.exec(content)) !== null) {
    itemsToAdd.push({ name: match[1], label: match[2] });
  }

  if (itemsToAdd.length > 0) {
    try {
      await db.execute('DELETE FROM items');

      const chunkSize = 100;
      for (let i = 0; i < itemsToAdd.length; i += chunkSize) {
        const chunk = itemsToAdd.slice(i, i + chunkSize);
        const batchStatements = chunk.map(item => ({
          sql: 'INSERT INTO items (name, label) VALUES (?, ?)',
          args: [item.name, item.label]
        }));
        await db.batch(batchStatements, 'write');
      }

      res.render('admin_upload', { user: req.user, message: `นำเข้าไอเทมเรียบร้อยแล้วทั้งหมด ${itemsToAdd.length} รายการ` });
    } catch (err) {
      console.error(err);
      res.render('admin_upload', { user: req.user, message: 'เกิดข้อผิดพลาดในการบันทึกข้อมูลลงฐานข้อมูล' });
    }
  } else {
    res.render('admin_upload', { user: req.user, message: 'ไม่พบรูปแบบข้อมูล name และ label ในไฟล์ SQL นี้' });
  }
});

app.get('/admin/users', requireAdmin, async (req, res) => {
  try {
    const result = await db.execute('SELECT id, username, role FROM users');
    res.render('admin_users', { user: req.user, users: result.rows, message: null });
  } catch (err) {
    console.error(err);
    res.render('admin_users', { user: req.user, users: [], message: 'ไม่สามารถดึงข้อมูลผู้ใช้ได้' });
  }
});

app.post('/admin/users/add', requireAdmin, async (req, res) => {
  const { username, password, role } = req.body;
  try {
    const hashedPassword = bcrypt.hashSync(password, 10);
    await db.execute({
      sql: 'INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
      args: [username, hashedPassword, role]
    });
    res.redirect('/admin/users');
  } catch (err) {
    console.error(err);
    const result = await db.execute('SELECT id, username, role FROM users');
    res.render('admin_users', { user: req.user, users: result.rows, message: 'ชื่อผู้ใช้นี้มีอยู่ในระบบแล้ว หรือเกิดข้อผิดพลาด' });
  }
});

app.post('/admin/users/delete/:id', requireAdmin, async (req, res) => {
  const deleteId = parseInt(req.params.id);
  if (deleteId !== req.user.id) {
    try {
      await db.execute({
        sql: 'DELETE FROM users WHERE id = ?',
        args: [deleteId]
      });
    } catch (err) {
      console.error(err);
    }
  }
  res.redirect('/admin/users');
});

module.exports.handler = serverless(app);
