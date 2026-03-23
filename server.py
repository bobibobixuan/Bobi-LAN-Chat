import socket
import threading

# 服务器配置
HOST = '0.0.0.0'
PORT = 5000
UDP_PORT = 5002  # 用于自动发现的UDP端口

online_clients = {}
clients_lock = threading.Lock()

def udp_discovery_server():
    """监听UDP广播，当客户端寻找服务器时自动举手应答"""
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_socket.bind(('', UDP_PORT))
    print(f"UDP 发现服务已启动，监听端口：{UDP_PORT}")
    
    while True:
        try:
            data, addr = udp_socket.recvfrom(1024)
            if data == b'DISCOVER_BOBBY':
                response = f"BOBBY_HERE:{PORT}".encode('utf-8')
                udp_socket.sendto(response, addr)
        except Exception:
            pass

def broadcast_message(message, sender_socket=None):
    with clients_lock:
        sockets_to_send = list(online_clients.keys())

    for client_socket in sockets_to_send:
        try:
            client_socket.send(message.encode('utf-8'))
        except Exception:
            remove_client(client_socket)

def remove_client(client_socket):
    username = None
    with clients_lock:
        if client_socket in online_clients:
            username = online_clients.pop(client_socket)
            current_count = len(online_clients)
            
    if username:
        broadcast_message(f"【系统】{username} 离开了交流论坛，当前在线：{current_count}人")
        try:
            client_socket.close()
        except:
            pass

def handle_client(client_socket, client_addr):
    username = ""
    try:
        username = client_socket.recv(1024).decode('utf-8').strip()
        if not username:
            client_socket.close()
            return
        
        with clients_lock:
            online_clients[client_socket] = username
            current_count = len(online_clients)
            
        join_msg = f"【系统】{username} 加入了交流论坛，当前在线：{current_count}人"
        print(join_msg)
        broadcast_message(join_msg)

        while True:
            # 扩大缓冲区至 64KB，并允许替换无法解码的字符，防止发长段代码时报错掉线
            received_msg = client_socket.recv(65536).decode('utf-8', errors='replace').strip()
            if not received_msg:
                break
                
            full_msg = f"{username}: {received_msg}"
            print(full_msg)
            broadcast_message(full_msg)

    except (ConnectionResetError, ConnectionAbortedError):
        print(f"[{client_addr}] 意外断开连接")
    except Exception as e:
        print(f"处理客户端 [{client_addr}] 时出错: {e}")
    finally:
        remove_client(client_socket)

def start_server():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    # 启动UDP自动发现线程
    threading.Thread(target=udp_discovery_server, daemon=True).start()
    
    try:
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)
        print("="*40)
        print("【波比学习交流论坛】服务器已启动")
        print(f"TCP 聊天端口：{PORT}")
        print(f"已开启局域网自动发现功能，同学们可以直接点击【自动寻找】")
        print("="*40)

        while True:
            client_socket, client_addr = server_socket.accept()
            print(f"新同学连接：{client_addr}")
            client_thread = threading.Thread(target=handle_client, args=(client_socket, client_addr))
            client_thread.daemon = True 
            client_thread.start()
            
    except KeyboardInterrupt:
        print("\n服务器正在关闭...")
    finally:
        server_socket.close()

if __name__ == "__main__":
    start_server()