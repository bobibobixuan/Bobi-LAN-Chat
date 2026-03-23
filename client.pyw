import os
import random
import socket
import threading
import time
import tempfile
import shutil
import base64
import io
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

try:
    from PIL import Image, ImageTk, ImageDraw
except ImportError:
    messagebox.showerror("缺少依赖", "请在终端中运行 'pip install pillow'！")
    exit()

try:
    from ctypes import windll
    windll.shcore.SetProcessDpiAwareness(1)
except Exception: pass

class LanChatClient:
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("波比学习交流论坛 V2.0")
        self.root.geometry("1000x700") 
        self.root.resizable(True, True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.client_socket = None
        self.is_connected = False
        self.username = ""
        self.my_avatar_b64 = "" 
        self.chat_images = [] 
        self.user_list_images = [] 
        self.private_windows = {} 
        
        self.server_ip = tk.StringVar(value="")
        self.server_port = tk.StringVar(value="5000")
        
        self.placeholder_avatar = "R0lGODlhIAAgAMIFAAAAAD8/P09PT29vb4+Pj7+/v9/f3////yH5BAEKAAcALAAAAAAgACAAAAOBeLrc/jDKSau9OOvNu/9gqHGiSI5oqq5s675wLM90bd94ru987//AoHBILBqPyKRyyWw6n9CodEqtWq/YrHbL7Xq/4LB4TC6bz+i0es1uu9/wuHxOr9vv+Lx+z+/7/4CBgoOEhYaHiImKi4yNjo+QkZKTlJWWl5iZmpucnZ6foKGio6SlAQA7"
        
        self._init_menu()
        self._init_ui()
        
        self.root.after(500, self._startup_auto_search)

    def _init_menu(self):
        menubar = tk.Menu(self.root)
        
        account_menu = tk.Menu(menubar, tearoff=0)
        account_menu.add_command(label="👤 登录 / 注册", command=self.open_auth_window)
        account_menu.add_command(label="⚙️ 个人信息设置", command=self.open_profile_window)
        menubar.add_cascade(label=" 账号 ", menu=account_menu)

        sys_menu = tk.Menu(menubar, tearoff=0)
        sys_menu.add_command(label="🌐 网络与连接设置", command=self.open_network_settings)
        sys_menu.add_separator()
        sys_menu.add_command(label="❌ 退出论坛", command=self.on_closing)
        menubar.add_cascade(label=" 系统 ", menu=sys_menu)
        
        self.root.config(menu=menubar)

    def _init_ui(self):
        style = ttk.Style()
        if "clam" in style.theme_names(): style.theme_use("clam")
        self.root.configure(bg="#f3f4f6")  
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)

        main_paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL, bg="#f3f4f6", sashwidth=5)
        main_paned.grid(row=0, column=0, padx=15, pady=(15, 10), sticky="nsew")

        self.chat_canvas = tk.Canvas(main_paned, bg="#f5f5f5", highlightthickness=0)
        chat_scrollbar = ttk.Scrollbar(main_paned, orient="vertical", command=self.chat_canvas.yview)
        self.chat_interior = tk.Frame(self.chat_canvas, bg="#f5f5f5")
        self.chat_interior_id = self.chat_canvas.create_window((0,0), window=self.chat_interior, anchor="nw")
        self.chat_interior.bind("<Configure>", lambda e: self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all")))
        self.chat_canvas.bind("<Configure>", lambda e: self.chat_canvas.itemconfig(self.chat_interior_id, width=e.width))
        self.chat_canvas.configure(yscrollcommand=chat_scrollbar.set)
        
        main_paned.add(self.chat_canvas, stretch="always")
        main_paned.add(chat_scrollbar, stretch="never")

        list_frame = tk.Frame(main_paned, bg="#ffffff", bd=1, relief="ridge")
        main_paned.add(list_frame, minsize=200, stretch="never")
        
        ttk.Label(list_frame, text="🟢 在线同学", background="#ffffff", font=("微软雅黑", 11, "bold")).pack(pady=12)
        
        self.user_canvas = tk.Canvas(list_frame, bg="#ffffff", highlightthickness=0, width=240)
        user_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.user_canvas.yview)
        self.user_interior = tk.Frame(self.user_canvas, bg="#ffffff")
        self.user_interior_id = self.user_canvas.create_window((0,0), window=self.user_interior, anchor="nw")
        self.user_interior.bind("<Configure>", lambda e: self.user_canvas.configure(scrollregion=self.user_canvas.bbox("all")))
        self.user_canvas.bind("<Configure>", lambda e: self.user_canvas.itemconfig(self.user_interior_id, width=e.width))
        self.user_canvas.configure(yscrollcommand=user_scrollbar.set)
        
        self.user_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        user_scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

        frame_input = tk.Frame(self.root, bg="#f3f4f6")
        frame_input.grid(row=1, column=0, padx=15, pady=(0, 15), sticky="ew")
        frame_input.grid_columnconfigure(0, weight=1)

        self.entry_msg = ttk.Entry(frame_input, font=("微软雅黑", 12), state="disabled")
        self.entry_msg.grid(row=0, column=0, padx=(0, 10), ipady=8, sticky="ew") 
        self.entry_msg.bind("<Return>", lambda event: self.send_message()) 

        self.btn_send_img = ttk.Button(frame_input, text="🖼️ 发图片", width=10, command=self.send_image, state="disabled")
        self.btn_send_img.grid(row=0, column=1, padx=(0, 6), ipady=6)

        self.btn_send_file = ttk.Button(frame_input, text="📁 共享资料", width=12, command=self.share_file, state="disabled")
        self.btn_send_file.grid(row=0, column=2, padx=(0, 6), ipady=6)

        self.btn_send = ttk.Button(frame_input, text="发送 ↵", width=10, command=self.send_message, state="disabled")
        self.btn_send.grid(row=0, column=3, ipady=6)

    def _startup_auto_search(self):
        self._append_system_msg("雷达启动：正在机房网络中自动搜寻 Bobi 服务器...")
        def discover():
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            udp_socket.settimeout(2.0) 
            found = False
            start_time = time.time()
            
            while time.time() - start_time < 30: 
                try:
                    udp_socket.sendto(b'DISCOVER_BOBI', ('255.255.255.255', 5002))
                    data, addr = udp_socket.recvfrom(1024)
                    if data.startswith(b'BOBI_HERE'):
                        self.server_ip.set(addr[0])
                        self.server_port.set(data.decode('utf-8').split(':')[1])
                        found = True
                        break
                except: pass
            
            udp_socket.close()
            if found:
                self.root.after(0, self._append_system_msg, f"服务器已找到 ({self.server_ip.get()})！请登录。")
                self.root.after(500, self.open_auth_window)
            else:
                self.root.after(0, self._append_system_msg, "30秒未搜寻到服务器。请检查网络，或在顶部菜单栏【系统 -> 网络与连接设置】中处理。")
        
        threading.Thread(target=discover, daemon=True).start()

    def open_network_settings(self):
        net_win = tk.Toplevel(self.root)
        net_win.title("网络与连接设置")
        net_win.geometry("380x300")
        net_win.configure(bg="#f3f4f6")
        net_win.transient(self.root) 
        net_win.grab_set() 
        
        frame_manual = tk.LabelFrame(net_win, text=" 手动配置服务器 ", bg="#f3f4f6", font=("微软雅黑", 10, "bold"), fg="#374151")
        frame_manual.pack(fill=tk.X, padx=15, pady=15, ipady=5)
        
        tk.Label(frame_manual, text="服务器 IP:", bg="#f3f4f6", font=("微软雅黑", 10)).grid(row=0, column=0, padx=(15, 5), pady=10, sticky="e")
        ttk.Entry(frame_manual, textvariable=self.server_ip, font=("微软雅黑", 11), width=18).grid(row=0, column=1, padx=5, pady=10)
        
        tk.Label(frame_manual, text="端口:", bg="#f3f4f6", font=("微软雅黑", 10)).grid(row=1, column=0, padx=(15, 5), pady=5, sticky="e")
        ttk.Entry(frame_manual, textvariable=self.server_port, font=("微软雅黑", 11), width=18).grid(row=1, column=1, padx=5, pady=5)
        
        frame_auto = tk.Frame(net_win, bg="#f3f4f6")
        frame_auto.pack(fill=tk.X, padx=15, pady=5)
        
        btn_search = ttk.Button(frame_auto, text="🔍 自动雷达搜索服务器", command=lambda: self._trigger_manual_search(btn_search, net_win))
        btn_search.pack(fill=tk.X, ipady=6)
        
        ttk.Button(net_win, text="💾 保存并关闭", command=net_win.destroy).pack(pady=15, ipady=4)

    def _trigger_manual_search(self, btn, window):
        btn.config(state="disabled", text="正在局域网中搜寻... (最长30秒)")
        window.update()
        
        def discover():
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            udp_socket.settimeout(2.0) 
            found = False
            start_time = time.time()
            
            while time.time() - start_time < 30: 
                try:
                    udp_socket.sendto(b'DISCOVER_BOBI', ('255.255.255.255', 5002))
                    data, addr = udp_socket.recvfrom(1024)
                    if data.startswith(b'BOBI_HERE'):
                        self.root.after(0, lambda ip=addr[0], port=data.decode('utf-8').split(':')[1]: (self.server_ip.set(ip), self.server_port.set(port)))
                        found = True
                        break
                except: pass
            
            udp_socket.close()
            def reset_btn():
                btn.config(state="normal", text="🔍 自动雷达搜索服务器")
                if found: 
                    messagebox.showinfo("搜索成功", f"太棒了！已自动填入服务器地址：{self.server_ip.get()}", parent=window)
                else: 
                    messagebox.showwarning("搜索失败", "未在机房网络中发现服务器。\n\n解决方案：\n1. 检查网线或 WiFi 是否连接。\n2. 举手询问管理员 获取 IP 地址手动填写。", parent=window)
            self.root.after(0, reset_btn)
            
        threading.Thread(target=discover, daemon=True).start()

    def show_toast(self, title, message):
        if self.root.focus_displayof(): return 
        
        toast = tk.Toplevel(self.root)
        toast.overrideredirect(True) 
        toast.attributes('-topmost', True)
        toast.configure(bg="#ffffff", bd=1, relief="ridge")
        
        screen_w = toast.winfo_screenwidth()
        screen_h = toast.winfo_screenheight()
        toast.geometry(f"280x80+{screen_w - 300}+{screen_h - 150}")
        
        tk.Label(toast, text=title, font=("微软雅黑", 10, "bold"), bg="#ffffff", fg="#10b981").pack(anchor="w", padx=10, pady=(10, 0))
        tk.Label(toast, text=message[:30] + ("..." if len(message)>30 else ""), font=("微软雅黑", 9), bg="#ffffff", fg="#333333").pack(anchor="w", padx=10, pady=(5, 10))
        
        self.root.after(3500, toast.destroy)

    def _on_mousewheel(self, event):
        try:
            widget = self.root.winfo_containing(event.x_root, event.y_root)
            if widget:
                if str(self.user_canvas) in str(widget) or str(self.user_interior) in str(widget):
                    self.user_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                elif str(self.chat_canvas) in str(widget) or str(self.chat_interior) in str(widget):
                    self.chat_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                else:
                    for target, p_win in self.private_windows.items():
                        if p_win.winfo_exists():
                            if str(p_win.canvas) in str(widget) or str(p_win.interior) in str(widget):
                                p_win.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
                                break
        except: pass

    def safe_send(self, sock, msg):
        try: sock.send((msg + "<EOF>").encode('utf-8'))
        except: pass

    def _create_avatar_widget(self, parent_frame, username, avatar_b64, size=42, bg_color_hex="#f5f5f5", img_cache_list=None):
        if img_cache_list is None: img_cache_list = self.chat_images
        canvas = tk.Canvas(parent_frame, width=size, height=size, bg=bg_color_hex, highlightthickness=0)
        loaded_img = None
        
        if avatar_b64 and avatar_b64 != self.placeholder_avatar and len(avatar_b64) > 100: 
            try:
                img_data = base64.b64decode(avatar_b64)
                pil_img = Image.open(io.BytesIO(img_data)).convert("RGBA")
                pil_img = pil_img.resize((size, size), Image.Resampling.LANCZOS)
                mask = Image.new('L', (size, size), 0)
                draw = ImageDraw.Draw(mask)
                draw.ellipse((0, 0, size, size), fill=255) 
                result_img = Image.new('RGBA', (size, size), (0, 0, 0, 0)) 
                result_img.paste(pil_img, (0, 0), mask) 
                tk_img = ImageTk.PhotoImage(result_img)
                img_cache_list.append(tk_img) 
                loaded_img = tk_img
            except Exception: pass
                
        if loaded_img: 
            canvas.create_image(size//2, size//2, image=loaded_img)
        else:
            colors = ["#1890ff", "#52c41a", "#faad14", "#f5222d", "#722ed1", "#eb2f96", "#13c2c2"]
            bg_color = colors[sum(ord(c) for c in username) % len(colors)] if username else "#1890ff"
            canvas.create_oval(1, 1, size-1, size-1, fill=bg_color, outline="") 
            canvas.create_text(size//2, size//2, text=username[0].upper() if username else "?", fill="#ffffff", font=("微软雅黑", int(size*0.4), "bold"))
        return canvas

    def _compress_and_encode_image(self, filepath):
        img = Image.open(filepath).convert("RGB")
        img.thumbnail((150, 150), Image.Resampling.LANCZOS) 
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        return base64.b64encode(buffer.getvalue()).decode('utf-8')

    def _render_message(self, is_me, sender, avatar_b64, content, target_interior=None, target_canvas=None):
        if target_interior is None: target_interior = self.chat_interior
        if target_canvas is None: target_canvas = self.chat_canvas
        
        if "<<IMAGE>>" in content or "<<FILE>>" in content:
            self._handle_p2p_message(sender, content, avatar_b64, is_me, target_interior, target_canvas)
            return

        bg_color = target_interior.cget("bg")
        outer_frame = tk.Frame(target_interior, bg=bg_color, pady=8)
        outer_frame.pack(side=tk.TOP, fill=tk.X)
        avatar_widget = self._create_avatar_widget(outer_frame, sender, avatar_b64, size=42, bg_color_hex=bg_color)

        if is_me:
            avatar_widget.pack(side=tk.RIGHT, anchor=tk.N, padx=(10, 15)) 
            bubble_frame = tk.Frame(outer_frame, bg=bg_color)
            bubble_frame.pack(side=tk.RIGHT, anchor=tk.N)
            bubble = tk.Label(bubble_frame, text=content, bg="#95ec69", fg="#000000", font=("微软雅黑", 11), padx=14, pady=10, wraplength=400, justify="left", bd=0)
            bubble.pack(side=tk.TOP, anchor=tk.E)
        else:
            avatar_widget.pack(side=tk.LEFT, anchor=tk.N, padx=(15, 10))
            bubble_frame = tk.Frame(outer_frame, bg=bg_color)
            bubble_frame.pack(side=tk.LEFT, anchor=tk.N)
            tk.Label(bubble_frame, text=sender, bg=bg_color, fg="#888888", font=("微软雅黑", 9)).pack(side=tk.TOP, anchor=tk.W, pady=(0, 4))
            tk.Label(bubble_frame, text=content, bg="#ffffff", fg="#000000", font=("微软雅黑", 11), padx=14, pady=10, wraplength=400, justify="left", bd=0).pack(side=tk.TOP, anchor=tk.W)
            
        self.root.update_idletasks()
        target_canvas.yview_moveto(1.0)

    def _append_system_msg(self, msg, target_interior=None, target_canvas=None):
        if target_interior is None: target_interior = self.chat_interior
        if target_canvas is None: target_canvas = self.chat_canvas
        bg_color = target_interior.cget("bg")
        tk.Label(target_interior, text=f" {msg} ", bg=bg_color, fg="#9ca3af", font=("微软雅黑", 10, "italic"), pady=10).pack(side=tk.TOP, fill=tk.X, anchor=tk.CENTER)
        self.root.update_idletasks()
        target_canvas.yview_moveto(1.0)

    def _update_user_list(self, users_data_list):
        for widget in self.user_interior.winfo_children(): widget.destroy()
        self.user_list_images.clear() 
        
        for item in users_data_list:
            if not item: continue
            parts = item.split(",", 1)
            u = parts[0]
            av = parts[1] if len(parts) > 1 else ""
            
            if u == self.username and av and av != self.placeholder_avatar:
                self.my_avatar_b64 = av

            row_frame = tk.Frame(self.user_interior, bg="#ffffff", pady=5, cursor="hand2")
            row_frame.pack(side=tk.TOP, fill=tk.X)
            
            avatar_widget = self._create_avatar_widget(row_frame, u, av, size=32, bg_color_hex="#ffffff", img_cache_list=self.user_list_images)
            avatar_widget.pack(side=tk.LEFT, padx=(10, 8))
            
            display_text = f"{u} (我)" if u == self.username else u
            fg_color = "#10b981" if u == self.username else "#374151"
            font_weight = "bold" if u == self.username else "normal"
            
            name_label = tk.Label(row_frame, text=display_text, bg="#ffffff", fg=fg_color, font=("微软雅黑", 10, font_weight), cursor="hand2")
            name_label.pack(side=tk.LEFT)

            if u != self.username:
                row_frame.bind("<Double-1>", lambda e, target=u: self.open_private_chat(target))
                avatar_widget.bind("<Double-1>", lambda e, target=u: self.open_private_chat(target))
                name_label.bind("<Double-1>", lambda e, target=u: self.open_private_chat(target))

    def open_private_chat(self, target_user):
        if target_user in self.private_windows and self.private_windows[target_user].winfo_exists():
            self.private_windows[target_user].focus()
            return

        pm_win = tk.Toplevel(self.root)
        pm_win.title(f"💬 私聊 - {target_user}")
        pm_win.geometry("550x520")
        pm_win.configure(bg="#f3f4f6")
        
        header_frame = tk.Frame(pm_win, bg="#ffffff", bd=1, relief="ridge")
        header_frame.pack(side=tk.TOP, fill=tk.X, padx=12, pady=(12, 0))
        tk.Label(header_frame, text=f"🟢 正在与 {target_user} 私密聊天", bg="#ffffff", fg="#10b981", font=("微软雅黑", 11, "bold")).pack(pady=10)
        
        chat_outer = tk.Frame(pm_win, bg="#ffffff", bd=1, relief="ridge")
        chat_outer.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=12, pady=10)

        pm_canvas = tk.Canvas(chat_outer, bg="#f9fafb", highlightthickness=0)
        pm_scroll = ttk.Scrollbar(chat_outer, orient="vertical", command=pm_canvas.yview)
        pm_interior = tk.Frame(pm_canvas, bg="#f9fafb")
        pm_win_id = pm_canvas.create_window((0,0), window=pm_interior, anchor="nw")
        pm_interior.bind("<Configure>", lambda e: pm_canvas.configure(scrollregion=pm_canvas.bbox("all")))
        pm_canvas.bind("<Configure>", lambda e: pm_canvas.itemconfig(pm_win_id, width=e.width))
        pm_canvas.configure(yscrollcommand=pm_scroll.set)
        
        pm_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2, pady=2)
        pm_scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=2)

        input_frame = tk.Frame(pm_win, bg="#f3f4f6")
        input_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=(0, 15))
        
        entry_pm = ttk.Entry(input_frame, font=("微软雅黑", 12))
        entry_pm.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=8, padx=(0,10))
        
        def send_pm(event=None):
            msg = entry_pm.get().strip()
            if msg and self.is_connected:
                self.safe_send(self.client_socket, f"<<MSG_PRIVATE>>|{target_user}|{msg}")
                entry_pm.delete(0, tk.END)
                
        btn_send = ttk.Button(input_frame, text="发送 ↵", width=10, command=send_pm)
        btn_send.pack(side=tk.RIGHT, ipady=6)
        entry_pm.bind("<Return>", send_pm)

        pm_win.canvas = pm_canvas
        pm_win.interior = pm_interior
        self.private_windows[target_user] = pm_win

    def open_auth_window(self):
        if self.is_connected: return
        ip, port = self.server_ip.get().strip(), self.server_port.get().strip()
        if not ip or not port:
            messagebox.showerror("错误", "请先在【设置->网络设置】中指定服务器地址！")
            return
            
        auth_win = tk.Toplevel(self.root)
        auth_win.title("登录中心")
        auth_win.geometry("360x320")
        auth_win.transient(self.root) 
        auth_win.grab_set() 
        
        selected_avatar_b64 = [""] 
        
        def choose_avatar():
            filepath = filedialog.askopenfilename(title="选择头像", filetypes=[("图片", "*.png;*.gif;*.jpg;*.jpeg")], parent=auth_win)
            if not filepath: return
            if os.path.getsize(filepath) > 5 * 1024 * 1024:
                messagebox.showerror("文件太大", "头像请不要超过 5MB！", parent=auth_win)
                return
            try:
                selected_avatar_b64[0] = self._compress_and_encode_image(filepath)
                btn_avatar.config(text="✅ 高清头像已就绪")
            except Exception as e: messagebox.showerror("错误", f"解析失败: {e}", parent=auth_win)

        tk.Label(auth_win, text="账号:", font=("微软雅黑", 11)).pack(pady=(20, 5))
        entry_user = ttk.Entry(auth_win, font=("微软雅黑", 11))
        entry_user.pack()
        tk.Label(auth_win, text="密码:", font=("微软雅黑", 11)).pack(pady=5)
        entry_pwd = ttk.Entry(auth_win, show="*", font=("微软雅黑", 11))
        entry_pwd.pack()
        btn_avatar = ttk.Button(auth_win, text="[可选] 上传头像 (最高支持 5MB)", command=choose_avatar)
        btn_avatar.pack(pady=20)
        
        def do_auth(action):
            u, p = entry_user.get().strip(), entry_pwd.get().strip()
            if not u or not p or "|" in u or "," in u:
                messagebox.showerror("错误", "账号密码为空或包含非法字符", parent=auth_win)
                return
            try:
                temp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                temp_socket.settimeout(5)
                temp_socket.connect((ip, int(port)))
                req = f"<<{action}>>|{u}|{p}|{selected_avatar_b64[0]}" if action == "REGISTER" else f"<<LOGIN>>|{u}|{p}"
                self.safe_send(temp_socket, req)
                
                resp_raw = temp_socket.recv(4096).decode('utf-8')
                resp = resp_raw.split("<EOF>")[0]
                
                if resp.startswith("<<AUTH_SUCCESS>>"):
                    self.username = u
                    self.my_avatar_b64 = selected_avatar_b64[0] if selected_avatar_b64[0] else self.placeholder_avatar
                    self.client_socket = temp_socket
                    self._on_auth_success()
                    auth_win.destroy()
                else:
                    messagebox.showerror("认证失败", resp.replace("<<AUTH_FAIL>>", ""), parent=auth_win)
                    temp_socket.close()
            except Exception as e: messagebox.showerror("网络错误", f"连接失败: {e}", parent=auth_win)

        btn_frame = tk.Frame(auth_win)
        btn_frame.pack(pady=5)
        ttk.Button(btn_frame, text="登录", command=lambda: do_auth("LOGIN")).pack(side=tk.LEFT, padx=15)
        ttk.Button(btn_frame, text="注册", command=lambda: do_auth("REGISTER")).pack(side=tk.LEFT, padx=15)

    def _on_auth_success(self):
        self.is_connected = True
        self.client_socket.settimeout(None) 
        self.entry_msg.config(state="normal")
        self.btn_send.config(state="normal")
        self.btn_send_file.config(state="normal") 
        self.btn_send_img.config(state="normal") 
        self.entry_msg.focus() 
        self._append_system_msg("登录成功！正在同步历史聊天记录...")
        threading.Thread(target=self._receive_loop, daemon=True).start()

    def open_profile_window(self):
        if not self.is_connected:
            messagebox.showinfo("提示", "请先登录！")
            return
        prof_win = tk.Toplevel(self.root)
        prof_win.title("个人信息设置")
        prof_win.geometry("360x320")
        prof_win.transient(self.root) 
        prof_win.grab_set() 
        tk.Label(prof_win, text=f"当前账号: {self.username}", font=("微软雅黑", 13, "bold")).pack(pady=(20, 10))
        tk.Label(prof_win, text="新密码 (不修改请留空):", font=("微软雅黑", 11)).pack(pady=5)
        entry_pwd = ttk.Entry(prof_win, show="*", font=("微软雅黑", 11))
        entry_pwd.pack()
        selected_avatar_b64 = [""] 
        def choose_new_avatar():
            filepath = filedialog.askopenfilename(title="选择新头像", filetypes=[("图片", "*.png;*.gif;*.jpg;*.jpeg")], parent=prof_win)
            if not filepath: return
            try:
                selected_avatar_b64[0] = self._compress_and_encode_image(filepath)
                btn_avatar.config(text="✅ 新高清头像已处理就绪")
            except Exception as e: messagebox.showerror("错误", f"解析失败: {e}", parent=prof_win)

        btn_avatar = ttk.Button(prof_win, text="🖼️ 更换头像 (支持 5MB 内图片)", command=choose_new_avatar)
        btn_avatar.pack(pady=20)
        
        def save_profile():
            new_pwd = entry_pwd.get().strip()
            if not new_pwd and not selected_avatar_b64[0]:
                messagebox.showinfo("提示", "您没有进行任何修改", parent=prof_win)
                return
            try:
                req = f"<<UPDATE_PROFILE>>|{new_pwd}|{selected_avatar_b64[0]}"
                self.safe_send(self.client_socket, req)
                if selected_avatar_b64[0]: self.my_avatar_b64 = selected_avatar_b64[0]
                prof_win.destroy()
            except Exception as e: messagebox.showerror("错误", f"修改失败: {e}", parent=prof_win)

        ttk.Button(prof_win, text="💾 保存修改", command=save_profile).pack(pady=10)

    def _receive_loop(self):
        buffer = ""
        while self.is_connected:
            try:
                chunk = self.client_socket.recv(65536).decode('utf-8', errors='replace')
                if not chunk:
                    self.root.after(0, self._append_system_msg, "论坛服务器已关闭，您已断开连接")
                    break
                buffer += chunk
                while "<EOF>" in buffer:
                    msg, buffer = buffer.split("<EOF>", 1)
                    msg = msg.strip()
                    if not msg: continue
                    
                    if msg.startswith("【系统】"): 
                        self.root.after(0, self._append_system_msg, msg)
                    elif msg.startswith("<<USERS>>"):
                        users_raw = msg.replace("<<USERS>>", "")
                        users_list = users_raw.split("|") if users_raw else []
                        self.root.after(0, self._update_user_list, users_list)
                    elif msg.startswith("<<CHAT>>"):
                        parts = msg.split("|", 3)
                        if len(parts) == 4:
                            _, sender, avatar, content = parts
                            is_me = (sender == self.username)
                            self.root.after(0, self._render_message, is_me, sender, avatar, content)
                            if not is_me and "<<IMAGE>>" not in content and "<<FILE>>" not in content:
                                self.root.after(0, self.show_toast, f"群组新消息: {sender}", content)
                    elif msg.startswith("<<PRIVATE>>"):
                        parts = msg.split("|", 3)
                        if len(parts) == 4:
                            _, sender, avatar, content = parts
                            is_me = (sender == self.username)
                            
                            if not is_me:
                                self.root.after(0, self._handle_incoming_private_msg, sender, avatar, content)
                            else:
                                self.root.after(0, self._handle_outgoing_private_msg, avatar, content)

            except Exception as e:
                if self.is_connected: self.root.after(0, self._append_system_msg, f"网络异常退出: {e}")
                break
        self.root.after(0, self._reset_ui_safe)

    def _handle_incoming_private_msg(self, sender, avatar, content):
        if sender not in self.private_windows or not self.private_windows[sender].winfo_exists():
            self.open_private_chat(sender)
        
        p_win = self.private_windows.get(sender)
        if p_win:
            self._render_message(False, sender, avatar, content, p_win.interior, p_win.canvas)
            self.show_toast(f"💌 私聊消息: {sender}", content)

    def _handle_outgoing_private_msg(self, avatar, content):
        for p_name, p_win in list(self.private_windows.items()):
            if p_win.winfo_exists():
                self._render_message(True, self.username, avatar, content, p_win.interior, p_win.canvas)

    def send_message(self):
        if not self.is_connected: return
        msg_content = self.entry_msg.get().strip()
        if not msg_content: return
        self.btn_send.config(state="disabled")
        self.root.after(1000, lambda: self.btn_send.config(state="normal") if self.is_connected else None)
        try:
            self.safe_send(self.client_socket, msg_content)
            self.entry_msg.delete(0, tk.END) 
        except Exception as e: messagebox.showerror("发送失败", f"消息发送失败：{str(e)}")

    def get_local_ip(self):
        if self.client_socket:
            try: return self.client_socket.getsockname()[0]
            except: pass
        return '127.0.0.1'

    def _handle_p2p_message(self, sender, content, avatar_b64, is_me, target_interior, target_canvas):
        if "<<IMAGE>>" in content:
            parts = content.split("<<IMAGE>>")[1].split("|")
            if len(parts) == 4:
                filename, filesize, host_ip, file_port = parts
                if not is_me: 
                    self._append_system_msg(f"【{sender}】发出一张图片...", target_interior, target_canvas)
                    temp_path = os.path.join(tempfile.gettempdir(), f"bobi_img_{random.randint(1000,9999)}.png")
                    threading.Thread(target=self._auto_download_and_show_img, args=(host_ip, int(file_port), temp_path, is_me, avatar_b64, sender, target_interior, target_canvas), daemon=True).start()
                else: self._append_system_msg(f"图片发出成功。", target_interior, target_canvas)
        elif "<<FILE>>" in content:
            parts = content.split("<<FILE>>")[1].split("|")
            if len(parts) == 4:
                filename, filesize, host_ip, file_port = parts
                if not is_me: self.prompt_download_file(sender, filename, int(filesize), host_ip, int(file_port))
                else: self._append_system_msg(f"发起了资料共享：{filename}", target_interior, target_canvas)

    def _file_sender_thread(self, filepath, host_ip, file_port, share_type_desc):
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server.bind((host_ip, file_port))
            server.listen(15) 
            start_time = time.time()
            while time.time() - start_time < 60:
                try:
                    server.settimeout(1.0) 
                    conn, addr = server.accept()
                    def send_to_peer(connection, path):
                        try:
                            with open(path, 'rb') as f:
                                while True:
                                    chunk = f.read(4096)
                                    if not chunk: break
                                    connection.sendall(chunk)
                        except: pass
                        finally: connection.close()
                    threading.Thread(target=send_to_peer, args=(conn, filepath), daemon=True).start()
                except: continue 
        except: pass
        finally: server.close()

    def send_image(self):
        filepath = filedialog.askopenfilename(title="选择图片", filetypes=[("图片", "*.png;*.gif;*.jpg;*.jpeg")])
        if not filepath: return
        filename, filesize = os.path.basename(filepath), os.path.getsize(filepath)
        host_ip, file_port = self.get_local_ip(), random.randint(10000, 60000) 
        threading.Thread(target=self._file_sender_thread, args=(filepath, host_ip, file_port, "图片"), daemon=True).start()
        self.safe_send(self.client_socket, f"<<IMAGE>>{filename}|{filesize}|{host_ip}|{file_port}")
        self._display_image_in_chat(filepath, is_me=True, avatar_b64=self.my_avatar_b64, sender=self.username) 

    def _auto_download_and_show_img(self, host_ip, file_port, save_path, is_me, avatar_b64, sender, target_interior, target_canvas):
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client.settimeout(5) 
            client.connect((host_ip, file_port))
            with open(save_path, 'wb') as f:
                while True:
                    bytes_read = client.recv(4096)
                    if not bytes_read: break
                    f.write(bytes_read)
            self.root.after(0, self._display_image_in_chat, save_path, is_me, avatar_b64, sender, target_interior, target_canvas)
        except: self.root.after(0, self._append_system_msg, "图片已过期或被拦截。", target_interior, target_canvas)
        finally: client.close()

    def _display_image_in_chat(self, filepath, is_me=False, avatar_b64="", sender="", target_interior=None, target_canvas=None):
        if target_interior is None: target_interior = self.chat_interior
        if target_canvas is None: target_canvas = self.chat_canvas
        try:
            pil_img = Image.open(filepath).convert("RGBA")
            scale = max(pil_img.width // 200, 1)
            preview_pil = pil_img.resize((pil_img.width // scale, pil_img.height // scale), Image.Resampling.LANCZOS)
            preview_tk = ImageTk.PhotoImage(preview_pil)
            self.chat_images.append(preview_tk) 
            
            bg_color = target_interior.cget("bg")
            outer_frame = tk.Frame(target_interior, bg=bg_color, pady=8)
            outer_frame.pack(side=tk.TOP, fill=tk.X)
            avatar_widget = self._create_avatar_widget(outer_frame, sender, avatar_b64, size=42, bg_color_hex=bg_color)
            
            img_label = tk.Label(outer_frame, image=preview_tk, cursor="hand2", bg="#ffffff", bd=2, relief="groove")
            img_label.bind("<Button-1>", lambda e, path=filepath: self._open_image_viewer(path))

            if is_me:
                avatar_widget.pack(side=tk.RIGHT, anchor=tk.N, padx=(10, 15))
                bubble_frame = tk.Frame(outer_frame, bg=bg_color)
                bubble_frame.pack(side=tk.RIGHT, anchor=tk.N)
                img_label.pack(side=tk.TOP, anchor=tk.E)
            else:
                avatar_widget.pack(side=tk.LEFT, anchor=tk.N, padx=(15, 10))
                bubble_frame = tk.Frame(outer_frame, bg=bg_color)
                bubble_frame.pack(side=tk.LEFT, anchor=tk.N)
                tk.Label(bubble_frame, text=sender, bg=bg_color, fg="#888888", font=("微软雅黑", 9)).pack(side=tk.TOP, anchor=tk.W, pady=(0, 4))
                img_label.pack(side=tk.TOP, anchor=tk.W)
                
            self.root.update_idletasks()
            target_canvas.yview_moveto(1.0)
        except: pass

    def _open_image_viewer(self, filepath):
        viewer = tk.Toplevel(self.root)
        viewer.title("查看原图 (滚轮缩放，拖拽移动)")
        viewer.geometry("850x650")
        viewer.configure(bg="#222222")

        top_frame = tk.Frame(viewer, bg="#222222", pady=10)
        top_frame.pack(fill=tk.X)
        ttk.Button(top_frame, text="💾 另存为高清原图...", command=lambda: self._save_image_as(filepath, viewer)).pack()

        try:
            pil_img = Image.open(filepath).convert("RGBA")
            self.viewer_orig_img = pil_img
            self.viewer_scale = 1.0
            
            w, h = pil_img.size
            if w > 800 or h > 500:
                self.viewer_scale = min(800 / w, 500 / h)

            self.viewer_canvas = tk.Canvas(viewer, bg="#222222", highlightthickness=0)
            self.viewer_canvas.pack(fill=tk.BOTH, expand=True)
            
            self._redraw_viewer_image()

            self.viewer_canvas.bind("<MouseWheel>", self._viewer_zoom)
            self.viewer_canvas.bind("<ButtonPress-1>", self._viewer_start_pan)
            self.viewer_canvas.bind("<B1-Motion>", self._viewer_pan)

        except Exception as e: messagebox.showerror("错误", f"打开图片失败: {e}", parent=viewer)

    def _redraw_viewer_image(self):
        w, h = self.viewer_orig_img.size
        new_w, new_h = int(w * self.viewer_scale), int(h * self.viewer_scale)
        if new_w < 50 or new_h < 50: return 
        
        resized = self.viewer_orig_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        self.viewer_tk_img = ImageTk.PhotoImage(resized)
        
        self.viewer_canvas.delete("all")
        canvas_w = self.viewer_canvas.winfo_width()
        canvas_h = self.viewer_canvas.winfo_height()
        if canvas_w < 10: canvas_w, canvas_h = 850, 550 
        
        self.viewer_canvas.create_image(canvas_w//2, canvas_h//2, image=self.viewer_tk_img, anchor="center", tags="img")

    def _viewer_zoom(self, event):
        scale_factor = 1.1 if event.delta > 0 else 0.9
        self.viewer_scale *= scale_factor
        self._redraw_viewer_image()

    def _viewer_start_pan(self, event):
        self.viewer_canvas.scan_mark(event.x, event.y)

    def _viewer_pan(self, event):
        self.viewer_canvas.scan_dragto(event.x, event.y, gain=1)

    def _save_image_as(self, filepath, window):
        save_path = filedialog.asksaveasfilename(initialfile=os.path.basename(filepath), filetypes=[("图片", "*.png;*.gif;*.jpg;*.jpeg")])
        if save_path:
            try: shutil.copy2(filepath, save_path); messagebox.showinfo("成功", "保存成功！", parent=window)
            except Exception as e: messagebox.showerror("错误", f"保存失败: {e}", parent=window)

    def share_file(self):
        filepath = filedialog.askopenfilename(title="选择文件")
        if not filepath: return
        filename, filesize = os.path.basename(filepath), os.path.getsize(filepath)
        host_ip, file_port = self.get_local_ip(), random.randint(10000, 60000) 
        threading.Thread(target=self._file_sender_thread, args=(filepath, host_ip, file_port, "资料"), daemon=True).start()
        self.safe_send(self.client_socket, f"<<FILE>>{filename}|{filesize}|{host_ip}|{file_port}")

    def prompt_download_file(self, sender, filename, filesize, host_ip, file_port):
        mb_size = round(filesize / (1024 * 1024), 2)
        if messagebox.askyesno("收到共享资料", f"同学 [{sender}] 分享了资料：\n\n文件名: {filename}\n大小: {mb_size} MB\n\n是否立即接收？(60秒有效)"):
            save_path = filedialog.asksaveasfilename(initialfile=filename, title="保存资料到...")
            if save_path:
                self._append_system_msg(f"正在接收资料 {filename}...")
                threading.Thread(target=self._file_receiver_thread, args=(host_ip, file_port, save_path), daemon=True).start()

    def _file_receiver_thread(self, host_ip, file_port, save_path):
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client.settimeout(5)
            client.connect((host_ip, file_port))
            with open(save_path, 'wb') as f:
                while True:
                    bytes_read = client.recv(4096)
                    if not bytes_read: break
                    f.write(bytes_read)
            self.root.after(0, self._append_system_msg, f"资料接收成功！")
        except: self.root.after(0, self._append_system_msg, f"资料已过期。")
        finally: client.close()

    def _reset_ui_safe(self):
        self.is_connected = False
        for widget in self.user_interior.winfo_children(): widget.destroy() 
        if self.client_socket:
            try: self.client_socket.close()
            except: pass
        self.client_socket = None
        self.username = ""
        self.entry_msg.config(state="disabled")
        self.btn_send.config(state="disabled")
        self.btn_send_file.config(state="disabled")
        self.btn_send_img.config(state="disabled")

    def on_closing(self):
        if self.is_connected and self.client_socket:
            try: self.client_socket.close() 
            except: pass
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = LanChatClient(root)
    root.mainloop()