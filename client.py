import os
import random
import socket
import threading
import time
import tempfile
import shutil  # 用于图片另存为
import tkinter as tk
from tkinter import ttk, scrolledtext, simpledialog, messagebox, filedialog

class LanChatClient:
    def __init__(self, root_window):
        self.root = root_window
        self.root.title("波比学习交流论坛")
        self.root.geometry("850x600") 
        self.root.resizable(True, True)
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # 网络变量
        self.client_socket = None
        self.is_connected = False
        self.username = ""
        
        # 必须把图片存到列表里保活，防止被 Python 的垃圾回收机制清理导致白屏
        self.chat_images = [] 

        self._init_ui()

    def _init_ui(self):
        """现代化且呼吸感更强的网格布局"""
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")
            
        self.root.configure(bg="#f3f4f6")  
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # ---------------- 顶部：连接区域 ----------------
        frame_connect = tk.Frame(self.root, bg="#ffffff", bd=1, relief="ridge")
        frame_connect.grid(row=0, column=0, padx=15, pady=10, sticky="ew")
        frame_connect.grid_columnconfigure(1, weight=1)

        ttk.Label(frame_connect, text="服务器 IP:", background="#ffffff", font=("微软雅黑", 9)).grid(row=0, column=0, padx=(10, 2), pady=10)
        self.entry_ip = ttk.Entry(frame_connect, font=("微软雅黑", 10))
        self.entry_ip.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        ttk.Label(frame_connect, text="端口:", background="#ffffff", font=("微软雅黑", 9)).grid(row=0, column=2, padx=2, pady=10)
        self.entry_port = ttk.Entry(frame_connect, width=6, font=("微软雅黑", 10))
        self.entry_port.grid(row=0, column=3, padx=5, pady=10)
        self.entry_port.insert(0, "5000")

        self.btn_search = ttk.Button(frame_connect, text="🔍 一键寻找", command=self.search_server)
        self.btn_search.grid(row=0, column=4, padx=5, pady=10)

        self.btn_connect = ttk.Button(frame_connect, text="🚀 进入论坛", command=self.connect_server)
        self.btn_connect.grid(row=0, column=5, padx=(5, 10), pady=10)

        # ---------------- 中间：消息显示区 ----------------
        self.text_msg_area = scrolledtext.ScrolledText(
            self.root, state="disabled", wrap=tk.WORD, 
            font=("微软雅黑", 10), bg="#ffffff", fg="#333333", 
            padx=10, pady=10, borderwidth=0, highlightthickness=1, highlightcolor="#d1d5db"
        )
        self.text_msg_area.grid(row=1, column=0, padx=15, pady=(0, 10), sticky="nsew")

        # 颜色标签
        self.text_msg_area.tag_config("system", foreground="#9ca3af", font=("微软雅黑", 9, "italic")) 
        self.text_msg_area.tag_config("username", foreground="#3b82f6", font=("微软雅黑", 10, "bold")) 
        self.text_msg_area.tag_config("message", foreground="#1f2937", font=("微软雅黑", 10)) 

        # ---------------- 底部：消息输入区 ----------------
        frame_input = tk.Frame(self.root, bg="#f3f4f6")
        frame_input.grid(row=2, column=0, padx=15, pady=(0, 15), sticky="ew")
        frame_input.grid_columnconfigure(0, weight=1)

        self.entry_msg = ttk.Entry(frame_input, font=("微软雅黑", 11), state="disabled")
        self.entry_msg.grid(row=0, column=0, padx=(0, 10), ipady=5, sticky="ew") 
        self.entry_msg.bind("<Return>", lambda event: self.send_message()) 

        self.btn_send_img = ttk.Button(frame_input, text="🖼️ 发图片", command=self.send_image, state="disabled")
        self.btn_send_img.grid(row=0, column=1, padx=(0, 5), ipady=3)

        self.btn_send_file = ttk.Button(frame_input, text="📁 共享资料", command=self.share_file, state="disabled")
        self.btn_send_file.grid(row=0, column=2, padx=(0, 5), ipady=3)

        self.btn_send = ttk.Button(frame_input, text="发送 ↵", command=self.send_message, state="disabled")
        self.btn_send.grid(row=0, column=3, ipady=3)

    # ================= 自动寻找服务器 =================
    def search_server(self):
        self.btn_search.config(state="disabled", text="正在寻找...")
        self.root.update()

        def discover():
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            udp_socket.settimeout(2.0) 
            try:
                udp_socket.sendto(b'DISCOVER_BOBBY', ('255.255.255.255', 5002))
                data, addr = udp_socket.recvfrom(1024)
                if data.startswith(b'BOBBY_HERE'):
                    server_ip = addr[0]
                    server_port = data.decode('utf-8').split(':')[1]
                    self.root.after(0, self._auto_fill_server, server_ip, server_port)
            except socket.timeout:
                self.root.after(0, lambda: messagebox.showwarning("未找到", "没有找到论坛服务器，请尝试手动输入IP。"))
            except Exception as e:
                pass
            finally:
                udp_socket.close()
                self.root.after(0, lambda: self.btn_search.config(state="normal", text="🔍 一键寻找"))

        threading.Thread(target=discover, daemon=True).start()

    def _auto_fill_server(self, ip, port):
        self.entry_ip.delete(0, tk.END)
        self.entry_ip.insert(0, ip)
        self.entry_port.delete(0, tk.END)
        self.entry_port.insert(0, port)
        messagebox.showinfo("好消息", f"已成功找到波比的论坛服务器！\nIP地址: {ip}")

    # ================= 核心网络通信 =================
    def _append_msg_safe(self, msg):
        self.text_msg_area.config(state="normal")
        if msg.startswith("【系统】"):
            self.text_msg_area.insert(tk.END, msg + "\n", "system")
        elif ": " in msg:
            username, content = msg.split(": ", 1)
            self.text_msg_area.insert(tk.END, username + ": ", "username")
            self.text_msg_area.insert(tk.END, content + "\n", "message")
        else:
            self.text_msg_area.insert(tk.END, msg + "\n", "message")
        self.text_msg_area.yview(tk.END) 
        self.text_msg_area.config(state="disabled")

    def get_local_ip(self):
        """断网机房必备：直接获取与服务器通信时的真实网卡IP"""
        if self.client_socket:
            try:
                return self.client_socket.getsockname()[0]
            except: pass
        return '127.0.0.1'

    def connect_server(self):
        if self.is_connected: return

        server_ip = self.entry_ip.get().strip()
        server_port = self.entry_port.get().strip()
        if not server_ip or not server_port.isdigit():
            messagebox.showerror("错误", "请先填写IP和端口")
            return
        server_port = int(server_port)

        username = simpledialog.askstring("论坛昵称", "起个响亮的名字吧：", parent=self.root)
        if not username or username.strip() == "": return
        self.username = username.strip()

        try:
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(5)
            self.client_socket.connect((server_ip, server_port))
            self.client_socket.settimeout(None) 
            self.client_socket.send(self.username.encode('utf-8')) 

            self.is_connected = True
            self.btn_connect.config(state="disabled", text="✅ 已进入论坛")
            self.btn_search.config(state="disabled")
            self.entry_ip.config(state="disabled")
            self.entry_port.config(state="disabled")
            self.entry_msg.config(state="normal")
            self.btn_send.config(state="normal")
            self.btn_send_file.config(state="normal") 
            self.btn_send_img.config(state="normal") 
            self.entry_msg.focus() 

            threading.Thread(target=self._receive_loop, daemon=True).start()

        except Exception as e:
            messagebox.showerror("连接失败", f"无法连接论坛：{str(e)}")

    def _receive_loop(self):
        while self.is_connected:
            try:
                # 64KB大缓冲区，防代码断连
                msg = self.client_socket.recv(65536).decode('utf-8', errors='replace')
                if not msg:
                    self.root.after(0, self._append_msg_safe, "【系统】论坛服务器已关闭，您已断开连接")
                    break
                
                # 拦截图片
                if "<<IMAGE>>" in msg:
                    parts = msg.split("<<IMAGE>>")
                    sender_name = parts[0].replace(":", "").strip()
                    file_info = parts[1].split("|")
                    if len(file_info) == 4:
                        filename, filesize, host_ip, file_port = file_info
                        if sender_name != self.username: 
                            self.root.after(0, self._append_msg_safe, f"【{sender_name}】分享了一张图片:")
                            temp_path = os.path.join(tempfile.gettempdir(), f"bobby_img_{random.randint(1000,9999)}.png")
                            threading.Thread(target=self._auto_download_and_show_img, args=(host_ip, int(file_port), temp_path), daemon=True).start()
                    continue 

                # 拦截文件
                if "<<FILE>>" in msg:
                    parts = msg.split("<<FILE>>")
                    sender_name = parts[0].replace(":", "").strip()
                    file_info = parts[1].split("|")
                    if len(file_info) == 4:
                        filename, filesize, host_ip, file_port = file_info
                        self.root.after(0, self.prompt_download_file, sender_name, filename, int(filesize), host_ip, int(file_port))
                    continue 
                
                self.root.after(0, self._append_msg_safe, msg)
            except Exception:
                if self.is_connected:
                    self.root.after(0, self._append_msg_safe, "【系统】网络异常，已退出论坛")
                break
                
        self.root.after(0, self._reset_ui_safe)

    def send_message(self):
        if not self.is_connected: return
        msg_content = self.entry_msg.get().strip()
        if not msg_content: return

        try:
            self.client_socket.send(msg_content.encode('utf-8'))
            self.entry_msg.delete(0, tk.END) 
            self.entry_msg.focus()
        except Exception as e:
            messagebox.showerror("发送失败", f"消息发送失败：{str(e)}")
            self._reset_ui_safe()

    # ================= P2P 分享核心逻辑 =================
    def _file_sender_thread(self, filepath, host_ip, file_port, share_type_desc):
        """后台发货线程（支持群内多人同时下载，维持60秒营业）"""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server.bind((host_ip, file_port))
            server.listen(15) 
            
            start_time = time.time()
            filename = os.path.basename(filepath)
            
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
                        except Exception: pass
                        finally:
                            connection.close()

                    threading.Thread(target=send_to_peer, args=(conn, filepath), daemon=True).start()
                    
                except socket.timeout:
                    continue 
                except Exception:
                    break
                    
            self.root.after(0, self._append_msg_safe, f"【系统】{share_type_desc} [{filename}] 下载通道已关闭。")
        except Exception as e:
            pass
        finally:
            server.close()

    # --- 发送/接收图片 ---
    def send_image(self):
        filepath = filedialog.askopenfilename(title="选择图片 (仅限PNG/GIF)", filetypes=[("Image Files", "*.png;*.gif")])
        if not filepath: return
            
        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)
        host_ip = self.get_local_ip()
        file_port = random.randint(10000, 60000) 

        threading.Thread(target=self._file_sender_thread, args=(filepath, host_ip, file_port, "图片"), daemon=True).start()

        share_msg = f"<<IMAGE>>{filename}|{filesize}|{host_ip}|{file_port}"
        self.client_socket.send(share_msg.encode('utf-8'))
        
        self._append_msg_safe(f"你发送了图片:")
        self._display_image_in_chat(filepath)

    def _auto_download_and_show_img(self, host_ip, file_port, save_path):
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client.settimeout(10) 
            client.connect((host_ip, file_port))
            with open(save_path, 'wb') as f:
                while True:
                    bytes_read = client.recv(4096)
                    if not bytes_read: break
                    f.write(bytes_read)
            self.root.after(0, self._display_image_in_chat, save_path)
        except Exception as e:
            self.root.after(0, self._append_msg_safe, f"【系统】图片接收失败，可能防火墙未关闭或存在网络隔离。")
        finally:
            client.close()

    def _display_image_in_chat(self, filepath):
        """将本地图片加载到聊天框中并实现可点击查看大图"""
        try:
            full_img = tk.PhotoImage(file=filepath)
            preview_img = full_img
            
            # 缩略图生成，防止大图撑爆聊天框
            if preview_img.width() > 300: 
                scale = preview_img.width() // 300 + 1
                preview_img = preview_img.subsample(scale, scale)
                
            self.chat_images.append(preview_img) 
            
            self.text_msg_area.config(state="normal")
            
            # 用 Label 包装图片，加上小手光标
            img_label = tk.Label(self.text_msg_area, image=preview_img, cursor="hand2", bg="#ffffff")
            img_label.bind("<Button-1>", lambda e, path=filepath: self._open_image_viewer(path))
            
            self.text_msg_area.window_create(tk.END, window=img_label)
            self.text_msg_area.insert(tk.END, "\n\n") 
            self.text_msg_area.yview(tk.END) 
            self.text_msg_area.config(state="disabled")
        except Exception as e:
            self.text_msg_area.insert(tk.END, f"[图片加载失败]\n")

    def _open_image_viewer(self, filepath):
        """打开独立窗口查看大图"""
        viewer = tk.Toplevel(self.root)
        viewer.title("查看原图")
        viewer.geometry("800x600")
        viewer.configure(bg="#e5e7eb")
        
        try:
            full_img = tk.PhotoImage(file=filepath)
            self.chat_images.append(full_img) 
            
            top_frame = tk.Frame(viewer, bg="#f3f4f6", pady=5)
            top_frame.pack(fill=tk.X)
            
            btn_save = ttk.Button(top_frame, text="💾 另存为图片...", command=lambda: self._save_image_as(filepath, viewer))
            btn_save.pack(pady=5)
            
            canvas = tk.Canvas(viewer, bg="#333333", highlightthickness=0)
            scroll_y = ttk.Scrollbar(viewer, orient="vertical", command=canvas.yview)
            scroll_x = ttk.Scrollbar(viewer, orient="horizontal", command=canvas.xview)
            
            canvas.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)
            
            scroll_y.pack(side="right", fill="y")
            scroll_x.pack(side="bottom", fill="x")
            canvas.pack(side="left", fill="both", expand=True)
            
            canvas.create_image(0, 0, image=full_img, anchor="nw")
            canvas.configure(scrollregion=canvas.bbox("all"))
            
        except Exception as e:
            tk.Label(viewer, text="大图加载失败", bg="#e5e7eb").pack(pady=20)

    def _save_image_as(self, filepath, window):
        """将临时文件夹中的图片复制保存到指定位置"""
        save_path = filedialog.asksaveasfilename(
            initialfile=os.path.basename(filepath),
            title="保存图片到...",
            filetypes=[("PNG/GIF 图片", "*.png;*.gif"), ("所有文件", "*.*")]
        )
        if save_path:
            try:
                shutil.copy2(filepath, save_path)
                messagebox.showinfo("成功", "图片保存成功！", parent=window)
            except Exception as e:
                messagebox.showerror("错误", f"保存失败: {e}", parent=window)

    # --- 发送/接收文件 ---
    def share_file(self):
        filepath = filedialog.askopenfilename(title="选择要共享给同学们的资料")
        if not filepath: return
            
        filename = os.path.basename(filepath)
        filesize = os.path.getsize(filepath)
        host_ip = self.get_local_ip()
        file_port = random.randint(10000, 60000) 

        threading.Thread(target=self._file_sender_thread, args=(filepath, host_ip, file_port, "资料"), daemon=True).start()

        share_msg = f"<<FILE>>{filename}|{filesize}|{host_ip}|{file_port}"
        self.client_socket.send(share_msg.encode('utf-8'))
        self._append_msg_safe(f"【系统】你发起了一份资料共享：{filename}，等待接收 (60秒有效)...")

    def prompt_download_file(self, sender, filename, filesize, host_ip, file_port):
        if sender == self.username: return 
            
        mb_size = round(filesize / (1024 * 1024), 2)
        ans = messagebox.askyesno("收到共享资料", f"同学 [{sender}] 分享了资料：\n\n文件名: {filename}\n大小: {mb_size} MB\n\n是否立即接收？")
        if ans:
            save_path = filedialog.asksaveasfilename(initialfile=filename, title="保存资料到...")
            if save_path:
                self._append_msg_safe(f"【系统】正在从 {sender} 处接收资料...")
                threading.Thread(target=self._file_receiver_thread, args=(host_ip, file_port, save_path), daemon=True).start()

    def _file_receiver_thread(self, host_ip, file_port, save_path):
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client.settimeout(10)
            client.connect((host_ip, file_port))
            with open(save_path, 'wb') as f:
                while True:
                    bytes_read = client.recv(4096)
                    if not bytes_read: break
                    f.write(bytes_read)
            filename = os.path.basename(save_path)
            self.root.after(0, self._append_msg_safe, f"【系统】资料 {filename} 接收成功！")
        except Exception as e:
            self.root.after(0, self._append_msg_safe, f"【系统】资料接收失败，可能网络隔离或超时。")
        finally:
            client.close()
    # ====================================================

    def _reset_ui_safe(self):
        self.is_connected = False
        if self.client_socket:
            try: self.client_socket.close()
            except: pass
        self.client_socket = None
        self.username = ""

        self.btn_connect.config(state="normal", text="🚀 进入论坛")
        self.btn_search.config(state="normal")
        self.entry_ip.config(state="normal")
        self.entry_port.config(state="normal")
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