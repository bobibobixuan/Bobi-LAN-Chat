import socket
import threading
import sqlite3
import time
import tkinter as tk
from tkinter import ttk
import tkinter.scrolledtext as st

HOST = '0.0.0.0'
PORT = 5000
UDP_PORT = 5002

online_clients = {} 
clients_lock = threading.Lock()
DEFAULT_AVATAR = "R0lGODlhIAAgAMIFAAAAAD8/P09PT29vb4+Pj7+/v9/f3////yH5BAEKAAcALAAAAAAgACAAAAOBeLrc/jDKSau9OOvNu/9gqHGiSI5oqq5s675wLM90bd94ru987//AoHBILBqPyKRyyWw6n9CodEqtWq/YrHbL7Xq/4LB4TC6bz+i0es1uu9/wuHxOr9vv+Lx+z+/7/4CBgoOEhYaHiImKi4yNjo+QkZKTlJWWl5iZmpucnZ6foKGio6SlAQA7"

class BobiServerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Bobi 论坛主控台 V2.0")
        self.root.geometry("600x450")
        self.root.configure(bg="#f3f4f6")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        self.is_running = True
        self._init_ui()
        
        # 启动服务器后台线程
        threading.Thread(target=start_server, args=(self,), daemon=True).start()

    def _init_ui(self):
        style = ttk.Style()
        if "clam" in style.theme_names(): style.theme_use("clam")
        
        # 顶部状态栏
        top_frame = tk.Frame(self.root, bg="#ffffff", bd=1, relief="ridge", pady=15)
        top_frame.pack(fill=tk.X, padx=15, pady=15)
        
        # 获取本机局域网IP，方便老师/管理员直接看到
        try:
            local_ip = socket.gethostbyname(socket.gethostname())
        except:
            local_ip = "未知"

        tk.Label(top_frame, text="🟢 服务器运行中", font=("微软雅黑", 14, "bold"), fg="#10b981", bg="#ffffff").pack(side=tk.LEFT, padx=20)
        
        info_text = f"本机 IP: {local_ip}  |  端口: {PORT}\nUDP 广播雷达: 活跃中 ({UDP_PORT})"
        tk.Label(top_frame, text=info_text, font=("微软雅黑", 10), fg="#6b7280", bg="#ffffff", justify="right").pack(side=tk.RIGHT, padx=20)

        # 实时日志面板
        log_frame = tk.Frame(self.root, bg="#f3f4f6")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))
        
        tk.Label(log_frame, text="📝 实时运行日志:", font=("微软雅黑", 10, "bold"), bg="#f3f4f6", fg="#374151").pack(anchor="w", pady=(0, 5))
        
        self.log_text = st.ScrolledText(log_frame, font=("Consolas", 10), bg="#1e1e1e", fg="#d4d4d4", bd=0, padx=10, pady=10)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.config(state=tk.DISABLED)
        
        self.log("========================================")
        self.log("🚀 Bobi 学习交流论坛 V2.0 旗舰版服务端启动")
        self.log("✅ 数据库 [bobi_forum.db] 挂载成功")
        self.log("✅ UDP 智能雷达广播已开启，等待客户端搜索...")
        self.log("========================================")

    def log(self, message):
        """线程安全的日志输出方法"""
        timestamp = time.strftime("[%H:%M:%S] ", time.localtime())
        def append():
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, timestamp + message + "\n")
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
        self.root.after(0, append)

    def on_closing(self):
        self.is_running = False
        self.root.destroy()
        os._exit(0) # 强制关闭所有子线程，干净利落退出

# ================= 核心逻辑区 =================
def init_db():
    conn = sqlite3.connect('bobi_forum.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT NOT NULL, avatar TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, sender TEXT, target TEXT DEFAULT 'ALL', content TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def save_message(sender, target, content):
    conn = sqlite3.connect('bobi_forum.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (sender, target, content) VALUES (?, ?, ?)", (sender, target, content))
    conn.commit()
    conn.close()

def get_history():
    conn = sqlite3.connect('bobi_forum.db')
    cursor = conn.cursor()
    cursor.execute('''SELECT m.sender, u.avatar, m.content FROM messages m LEFT JOIN users u ON m.sender = u.username WHERE m.target='ALL' ORDER BY m.id DESC LIMIT 30''')
    history = cursor.fetchall()
    conn.close()
    return reversed(history) 

def safe_send(sock, msg):
    try: sock.send((msg + "<EOF>").encode('utf-8'))
    except: pass

def handle_auth(client_socket, gui):
    buffer = ""
    while True:
        try:
            chunk = client_socket.recv(1024 * 50).decode('utf-8')
            if not chunk: return None
            buffer += chunk
            if "<EOF>" in buffer:
                req, buffer = buffer.split("<EOF>", 1)
                
                if req.startswith("<<REGISTER>>"):
                    parts = req.split("|", 3)
                    if len(parts) == 4: _, username, password, avatar = parts
                    else: _, username, password = parts[0], parts[1], parts[2]; avatar = DEFAULT_AVATAR
                    conn = sqlite3.connect('bobi_forum.db')
                    c = conn.cursor()
                    try:
                        c.execute("INSERT INTO users (username, password, avatar) VALUES (?, ?, ?)", (username, password, avatar))
                        conn.commit()
                        safe_send(client_socket, "<<AUTH_SUCCESS>>")
                        gui.log(f"👤 新用户注册成功: {username}")
                        return username
                    except sqlite3.IntegrityError:
                        safe_send(client_socket, "<<AUTH_FAIL>>用户名已存在！")
                    finally: conn.close()

                elif req.startswith("<<LOGIN>>"):
                    _, username, password = req.split("|")
                    with clients_lock:
                        if username in online_clients.values():
                            safe_send(client_socket, "<<AUTH_FAIL>>账号已在别处登录！")
                            continue
                    conn = sqlite3.connect('bobi_forum.db')
                    c = conn.cursor()
                    c.execute("SELECT password FROM users WHERE username=?", (username,))
                    result = c.fetchone()
                    conn.close()
                    if result and result[0] == password:
                        safe_send(client_socket, "<<AUTH_SUCCESS>>")
                        return username
                    else:
                        safe_send(client_socket, "<<AUTH_FAIL>>密码错误！")
        except: return None

def broadcast_user_list():
    with clients_lock:
        users = list(online_clients.values())
        sockets = list(online_clients.keys())
    user_data_list = []
    conn = sqlite3.connect('bobi_forum.db')
    c = conn.cursor()
    for u in users:
        c.execute("SELECT avatar FROM users WHERE username=?", (u,))
        res = c.fetchone()
        av = res[0] if res and res[0] else DEFAULT_AVATAR
        user_data_list.append(f"{u},{av}")
    conn.close()
    users_msg = "<<USERS>>" + "|".join(user_data_list)
    for sock in sockets: safe_send(sock, users_msg)

def broadcast_message(message):
    with clients_lock: sockets_to_send = list(online_clients.keys())
    for sock in sockets_to_send: safe_send(sock, message)

def send_private_message(sender, target, my_avatar, content, gui):
    target_socket = None
    sender_socket = None
    with clients_lock:
        for sock, uname in online_clients.items():
            if uname == target: target_socket = sock
            if uname == sender: sender_socket = sock
    
    msg_formatted = f"<<PRIVATE>>|{sender}|{my_avatar}|{content}"
    if target_socket: safe_send(target_socket, msg_formatted)
    if sender_socket and target_socket != sender_socket: safe_send(sender_socket, msg_formatted)
    save_message(sender, target, content)
    gui.log(f"💌 [私聊路由] {sender} -> {target}")

def remove_client(client_socket, gui):
    username = None
    with clients_lock:
        if client_socket in online_clients: username = online_clients.pop(client_socket)
    if username:
        gui.log(f"👋 {username} 下线了 (当前在线: {len(online_clients)} 人)")
        broadcast_message(f"【系统】{username} 离开了交流论坛。")
        broadcast_user_list()
        try: client_socket.close()
        except: pass

def get_user_avatar(username):
    conn = sqlite3.connect('bobi_forum.db')
    cursor = conn.cursor()
    cursor.execute("SELECT avatar FROM users WHERE username=?", (username,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result and result[0] else DEFAULT_AVATAR

def handle_client(client_socket, client_addr, gui):
    username = handle_auth(client_socket, gui)
    if not username:
        client_socket.close()
        return

    time.sleep(0.2) 
    for sender, avatar_b64, content in get_history():
        safe_send(client_socket, f"<<CHAT>>|{sender}|{avatar_b64}|{content}")
        time.sleep(0.01)

    with clients_lock: online_clients[client_socket] = username
    gui.log(f"🌐 {username} 成功上线，来自 {client_addr[0]} (当前在线: {len(online_clients)} 人)")
    
    broadcast_message(f"【系统】欢迎同学 [{username}] 上线！")
    broadcast_user_list()
    
    my_avatar = get_user_avatar(username)
    last_msg_time = 0
    buffer = ""

    try:
        while gui.is_running:
            chunk = client_socket.recv(65536).decode('utf-8', errors='replace')
            if not chunk: break
            buffer += chunk
            
            while "<EOF>" in buffer:
                received_msg, buffer = buffer.split("<EOF>", 1)
                received_msg = received_msg.strip()
                if not received_msg: continue

                if received_msg.startswith("<<UPDATE_PROFILE>>"):
                    parts = received_msg.split("|", 2)
                    if len(parts) == 3:
                        new_pwd, new_avatar = parts[1], parts[2]
                        conn = sqlite3.connect('bobi_forum.db')
                        c = conn.cursor()
                        if new_pwd and new_avatar:
                            c.execute("UPDATE users SET password=?, avatar=? WHERE username=?", (new_pwd, new_avatar, username))
                            my_avatar = new_avatar
                        elif new_pwd:
                            c.execute("UPDATE users SET password=? WHERE username=?", (new_pwd, username))
                        elif new_avatar:
                            c.execute("UPDATE users SET avatar=? WHERE username=?", (new_avatar, username))
                            my_avatar = new_avatar
                        conn.commit()
                        conn.close()
                        safe_send(client_socket, "【系统】个人信息保存成功！")
                        gui.log(f"⚙️ {username} 更新了个人资料")
                        broadcast_user_list() 
                    continue
                
                if received_msg.startswith("<<MSG_PRIVATE>>"):
                    parts = received_msg.split("|", 2)
                    if len(parts) == 3:
                        target_user, content = parts[1], parts[2]
                        send_private_message(username, target_user, my_avatar, content, gui)
                    continue

                current_time = time.time()
                if current_time - last_msg_time < 0.3: continue
                last_msg_time = current_time

                save_message(username, "ALL", received_msg)
                
                # 美化控制台的日志显示（不打印大段的图片Base64）
                display_msg = received_msg
                if "<<IMAGE>>" in display_msg: display_msg = "[发送了一张图片]"
                elif "<<FILE>>" in display_msg: display_msg = "[发送了一个共享文件]"
                gui.log(f"💬 大厅 | {username}: {display_msg}")
                
                broadcast_message(f"<<CHAT>>|{username}|{my_avatar}|{received_msg}")

    except Exception: pass
    finally: remove_client(client_socket, gui)

def udp_discovery_server(gui):
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_socket.bind(('', UDP_PORT))
    while gui.is_running:
        try:
            data, addr = udp_socket.recvfrom(1024)
            if data == b'DISCOVER_BOBI': 
                udp_socket.sendto(f"BOBI_HERE:{PORT}".encode('utf-8'), addr)
                # gui.log(f"📡 响应了来自 {addr[0]} 的 UDP 雷达搜索") # 如果嫌吵可以注释掉
        except: pass

def start_server(gui):
    init_db()
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    threading.Thread(target=udp_discovery_server, args=(gui,), daemon=True).start()
    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen(15)
        while gui.is_running:
            client_socket, client_addr = server_socket.accept()
            threading.Thread(target=handle_client, args=(client_socket, client_addr, gui), daemon=True).start()
    except Exception as e: 
        if gui.is_running: gui.log(f"❌ 服务器发生错误: {e}")
    finally: server_socket.close()

if __name__ == "__main__":
    import os # 解决关闭时的多线程退出问题
    root = tk.Tk()
    app = BobiServerGUI(root)
    root.mainloop()