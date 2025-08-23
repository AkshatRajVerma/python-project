import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
import json
import hashlib
import shutil
import sys
import traceback
import cv2
import face_recognition
import numpy as np
from PIL import Image, ImageTk
import secrets
from scipy.spatial import distance as dist

# --- Theme Configuration ---
BG_COLOR = "#F5F5F5"
FG_COLOR = "#333333"
BTN_BG_COLOR = "#007BFF"
BTN_FG_COLOR = "#FFFFFF"
ENTRY_BG_COLOR = "#FFFFFF"
SUCCESS_COLOR = "#28A745"
ERROR_COLOR = "#DC3545"
FONT_NORMAL = ("Calibri", 12)
FONT_BOLD = ("Calibri", 12, "bold")
FONT_TITLE = ("Calibri", 24, "bold")
FONT_SUBTITLE = ("Calibri", 14)

# --- Liveness and Verification Constants ---
EYE_AR_THRESH = 0.22
EYE_AR_CONSEC_FRAMES = 3
MATCH_STREAK_REQUIRED = 15
REJECT_STREAK_REQUIRED = 10

class SecureFileExplorer:
    def __init__(self, root):
        self.root = root
        self.root.title("Protecto - Secure File Explorer")
        self.root.geometry("900x700")
        self.root.configure(bg=BG_COLOR)

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        
        # --- File Paths ---
        self.users_file = "users.json"; self.permissions_file = "permissions.json"
        self.face_data_dir = "face_data"; self.secure_dir = "secure_files"
        for directory in [self.face_data_dir, self.secure_dir]:
            if not os.path.exists(directory): os.makedirs(directory)
        
        # --- State Management ---
        self.current_user = None; self.users = self.load_json(self.users_file, {})
        self.permissions = self.load_json(self.permissions_file, {})
        self.login_attempt_user = None; self.cap = None
        
        self.verification_state = "SEARCHING"
        self.match_streak = 0
        self.reject_streak = 0
        self.blink_counter = 0

        # --- Registration State ---
        self.reg_face_encodings = []; self.reg_capture_step = 0
        self.reg_capture_prompts = ["Look straight at the camera", "Turn your head slightly LEFT", "Turn your head slightly RIGHT"]
        
        self.setup_styles()
        self.setup_frames()
        self.show_frame('login_user')
    
    # --- Helper & Setup Functions ---
    def setup_styles(self):
        style = ttk.Style(); style.theme_use('clam')
        style.configure('TFrame', background=BG_COLOR); style.configure('TLabel', background=BG_COLOR, foreground=FG_COLOR, font=FONT_NORMAL)
        style.configure('Title.TLabel', background=BG_COLOR, foreground=BTN_BG_COLOR, font=FONT_TITLE)
        style.configure('Subtitle.TLabel', background=BG_COLOR, foreground=FG_COLOR, font=FONT_SUBTITLE)
        style.configure('Success.TLabel', background=BG_COLOR, foreground=SUCCESS_COLOR, font=FONT_BOLD)
        style.configure('Error.TLabel', background=BG_COLOR, foreground=ERROR_COLOR, font=FONT_BOLD)
        style.configure('Link.TLabel', foreground='blue', background=BG_COLOR, font=('Calibri', 10, 'underline'))
        style.configure('Header.TLabel', background=BG_COLOR, foreground=FG_COLOR, font=('Calibri', 16, 'bold'))
        style.configure('TLabelframe', background=BG_COLOR, bordercolor="#CCCCCC")
        style.configure('TLabelframe.Label', background=BG_COLOR, foreground=FG_COLOR, font=FONT_BOLD)
        style.configure('TButton', font=FONT_BOLD, padding=10, borderwidth=0)
        style.map('TButton', background=[('!active', BTN_BG_COLOR), ('active', '#0056b3')], foreground=[('active', BTN_FG_COLOR), ('!active', BTN_FG_COLOR)])
        style.configure('TEntry', fieldbackground=ENTRY_BG_COLOR, foreground=FG_COLOR, insertcolor=FG_COLOR, borderwidth=2, relief='flat')
        style.configure("Treeview", background=ENTRY_BG_COLOR, foreground=FG_COLOR, fieldbackground=ENTRY_BG_COLOR, rowheight=25, font=FONT_NORMAL)
        style.map("Treeview", background=[('selected', BTN_BG_COLOR)], foreground=[('selected', BTN_FG_COLOR)])
        style.configure("Treeview.Heading", font=FONT_BOLD, padding=5, background="#E1E1E1", foreground="#333333")

    def load_json(self, filename, default):
        try:
            with open(filename, 'r') as f: return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError): return default

    def save_json(self, filename, data):
        with open(filename, 'w') as f: json.dump(data, f, indent=4)

    def hash_value(self, value, salt=None):
        if salt is None: salt = secrets.token_hex(16)
        return f"{salt}${hashlib.sha256((salt + value).encode()).hexdigest()}"

    def verify_value(self, plain_value, hashed_string):
        try:
            salt, stored_hash = hashed_string.split('$')
            return self.hash_value(plain_value, salt) == hashed_string
        except: return False

    def eye_aspect_ratio(self, eye):
        return (dist.euclidean(eye[1], eye[5]) + dist.euclidean(eye[2], eye[4])) / (2.0 * dist.euclidean(eye[0], eye[3]))

    # --- Frame Creation ---
    def setup_frames(self):
        self.frames = {
            'login_user': self.create_login_user_frame(),
            'face_verification': self.create_face_verification_frame(),
            'password_login': self.create_password_login_frame(),
            'register': self.create_register_frame(),
            'file_explorer': self.create_file_explorer_frame(),
            'recovery_user': self.create_recovery_user_frame(),
            'recovery_questions': self.create_recovery_questions_frame(),
            'recovery_reset': self.create_recovery_reset_frame(),
        }

    def create_centered_frame(self):
        frame = ttk.Frame(self.root, style='TFrame')
        frame.grid_rowconfigure(0, weight=1); frame.grid_rowconfigure(2, weight=1)
        frame.grid_columnconfigure(0, weight=1); frame.grid_columnconfigure(2, weight=1)
        content_frame = ttk.Frame(frame, style='TFrame')
        content_frame.grid(row=1, column=1)
        return frame, content_frame

    def create_login_user_frame(self):
        frame, content = self.create_centered_frame()
        try:
            self.logo_img = ImageTk.PhotoImage(Image.open("logo.png").resize((128, 128)))
            ttk.Label(content, image=self.logo_img, style='TLabel').pack(pady=(0, 10))
        except FileNotFoundError: ttk.Label(content, text="Protecto", style='Title.TLabel').pack(pady=(0, 10))
        ttk.Label(content, text="Secure Sign In", style='Subtitle.TLabel').pack(pady=(0, 20))
        user_frame = ttk.Labelframe(content, text="Enter Username", style='TLabelframe')
        user_frame.pack(pady=10, padx=20, fill="x")
        self.login_user_var = tk.StringVar()
        ttk.Entry(user_frame, textvariable=self.login_user_var, width=40, font=FONT_NORMAL).pack(pady=15, padx=15)
        ttk.Button(content, text="Login with Face", command=self.start_face_login).pack(pady=10)
        reg_link = ttk.Label(content, text="Create Account", style='Link.TLabel', cursor="hand2")
        reg_link.pack(pady=20); reg_link.bind("<Button-1>", lambda e: self.show_frame('register'))
        return frame

    def create_face_verification_frame(self):
        frame, content = self.create_centered_frame()
        self.face_cam_label = ttk.Label(content, anchor="center")
        self.face_cam_label.pack(pady=10)
        self.face_status_label = ttk.Label(content, text="Initializing Camera...", font=FONT_BOLD)
        self.face_status_label.pack(pady=10)
        ttk.Button(content, text="Log in with Password Instead", command=self.show_password_login).pack(pady=10)
        return frame
    
    def create_password_login_frame(self):
        frame, content = self.create_centered_frame()
        ttk.Label(content, text="Password Required", style='Subtitle.TLabel').pack(pady=(0, 20))
        pass_frame = ttk.Labelframe(content, text="Enter Password", style='TLabelframe')
        pass_frame.pack(pady=10, padx=20, fill="x")
        self.pass_login_user_label = ttk.Label(pass_frame, text="Username: ...", style='TLabel')
        self.pass_login_user_label.pack(pady=5, padx=15, anchor='w')
        self.pass_login_var = tk.StringVar()
        ttk.Entry(pass_frame, textvariable=self.pass_login_var, show="*", width=40, font=FONT_NORMAL).pack(pady=10, padx=15)
        ttk.Button(content, text="Login", command=self.verify_password_login).pack(pady=10)
        links_frame = ttk.Frame(content, style='TFrame'); links_frame.pack(pady=10)
        back_link = ttk.Label(links_frame, text="< Back to Face Scan", style='Link.TLabel', cursor="hand2")
        back_link.pack(side=tk.LEFT, padx=10); back_link.bind("<Button-1>", lambda e: self.start_face_login())
        forgot_link = ttk.Label(links_frame, text="Forgot Password?", style='Link.TLabel', cursor="hand2")
        forgot_link.pack(side=tk.LEFT, padx=10); forgot_link.bind("<Button-1>", self.start_recovery_from_login)
        return frame
    
    def create_register_frame(self):
        frame, content = self.create_centered_frame()
        # Step 1
        self.reg_credentials_frame = ttk.Frame(content, style='TFrame')
        ttk.Label(self.reg_credentials_frame, text="Create Account", style='Title.TLabel').pack(pady=(0, 20))
        details_frame = ttk.Labelframe(self.reg_credentials_frame, text="Account Details", style='TLabelframe')
        details_frame.pack(pady=10, padx=20, fill="x")
        self.reg_username_var = tk.StringVar(); self.reg_password_var = tk.StringVar()
        ttk.Label(details_frame, text="Username:").grid(row=0, column=0, sticky='w', padx=10, pady=5)
        ttk.Entry(details_frame, textvariable=self.reg_username_var).grid(row=0, column=1, sticky='ew', padx=10, pady=5)
        ttk.Label(details_frame, text="Password:").grid(row=1, column=0, sticky='w', padx=10, pady=5)
        ttk.Entry(details_frame, textvariable=self.reg_password_var, show='*').grid(row=1, column=1, sticky='ew', padx=10, pady=5)
        ttk.Button(self.reg_credentials_frame, text="Next: Capture Face", command=self.start_face_capture_step).pack(pady=10)
        # Step 2
        self.reg_face_frame = ttk.Frame(content, style='TFrame')
        self.reg_face_prompt_label = ttk.Label(self.reg_face_frame, text="", style='Subtitle.TLabel')
        self.reg_face_prompt_label.pack(pady=(0,10))
        self.reg_cam_label = ttk.Label(self.reg_face_frame, anchor="center")
        self.reg_cam_label.pack(pady=10)
        self.reg_capture_btn = ttk.Button(self.reg_face_frame, text="Capture", command=self.process_face_capture)
        self.reg_capture_btn.pack(pady=10)
        # Step 3
        self.reg_security_frame = ttk.Frame(content, style='TFrame')
        ttk.Label(self.reg_security_frame, text="Set Up Account Recovery", style='Title.TLabel').pack(pady=(0, 20))
        sec_q_frame = ttk.Labelframe(self.reg_security_frame, text="Security Questions", style='TLabelframe')
        sec_q_frame.pack(pady=10, padx=20, fill="x")
        self.sec_q1_var = tk.StringVar(); self.sec_a1_var = tk.StringVar()
        self.sec_q2_var = tk.StringVar(); self.sec_a2_var = tk.StringVar()
        ttk.Label(sec_q_frame, text="Custom Question 1:").grid(row=0, column=0, sticky='w', padx=10, pady=5)
        ttk.Entry(sec_q_frame, textvariable=self.sec_q1_var).grid(row=0, column=1, sticky='ew', padx=10, pady=5)
        ttk.Label(sec_q_frame, text="Answer 1:").grid(row=1, column=0, sticky='w', padx=10, pady=5)
        ttk.Entry(sec_q_frame, textvariable=self.sec_a1_var, show='*').grid(row=1, column=1, sticky='ew', padx=10, pady=5)
        ttk.Label(sec_q_frame, text="Custom Question 2:").grid(row=2, column=0, sticky='w', padx=10, pady=5)
        ttk.Entry(sec_q_frame, textvariable=self.sec_q2_var).grid(row=2, column=1, sticky='ew', padx=10, pady=5)
        ttk.Label(sec_q_frame, text="Answer 2:").grid(row=3, column=0, sticky='w', padx=10, pady=5)
        ttk.Entry(sec_q_frame, textvariable=self.sec_a2_var, show='*').grid(row=3, column=1, sticky='ew', padx=10, pady=5)
        ttk.Button(self.reg_security_frame, text="Finish Registration", command=self.complete_registration).pack(pady=20)
        self.back_to_login_btn = ttk.Button(content, text="< Back to Login", command=self.logout)
        self.back_to_login_btn.pack(pady=20, side=tk.BOTTOM)
        return frame

    def create_file_explorer_frame(self):
        frame = ttk.Frame(self.root, padding="20"); top_frame = ttk.Frame(frame); top_frame.pack(fill=tk.X, pady=10)
        self.user_label = ttk.Label(top_frame, text="", style='Header.TLabel'); self.user_label.pack(side=tk.LEFT, padx=10)
        ttk.Button(top_frame, text="Logout", command=self.logout, width=10).pack(side=tk.RIGHT, padx=10)
        self.file_tree = ttk.Treeview(frame, columns=("Owner", "Access"), style="Treeview")
        self.file_tree.heading("#0", text="File Name"); self.file_tree.heading("Owner", text="Owner"); self.file_tree.heading("Access", text="Access Level")
        self.file_tree.column("#0", width=400); self.file_tree.pack(fill=tk.BOTH, expand=True, pady=10, padx=10)
        btn_frame = ttk.Frame(frame); btn_frame.pack(fill=tk.X, pady=10, padx=10)
        for text, command in [("Upload", self.upload_file), ("Download", self.download_file), ("Delete", self.delete_file), ("Share", self.share_file)]:
            ttk.Button(btn_frame, text=text, command=command).pack(side=tk.LEFT, padx=10)
        return frame
        
    def create_recovery_user_frame(self):
        frame, content = self.create_centered_frame()
        ttk.Label(content, text="Account Recovery", style='Title.TLabel').pack(pady=(0, 20))
        user_frame = ttk.Labelframe(content, text="Enter Username to Recover", style='TLabelframe')
        user_frame.pack(pady=10, padx=20, fill="x")
        self.recovery_user_var = tk.StringVar()
        ttk.Entry(user_frame, textvariable=self.recovery_user_var, width=40, font=FONT_NORMAL).pack(pady=15, padx=15)
        ttk.Button(content, text="Next", command=self.verify_recovery_user).pack(pady=10)
        ttk.Button(content, text="< Back to Login", command=self.logout).pack(pady=5)
        return frame

    def create_recovery_questions_frame(self):
        frame, content = self.create_centered_frame()
        ttk.Label(content, text="Answer Security Questions", style='Title.TLabel').pack(pady=(0, 20))
        sec_q_frame = ttk.Labelframe(content, text="Security Questions", style='TLabelframe')
        sec_q_frame.pack(pady=10, padx=20, fill="x")
        self.rec_q1_label = ttk.Label(sec_q_frame, text="Q1:"); self.rec_q1_label.grid(row=0, column=0, columnspan=2, sticky='w', padx=10, pady=5)
        self.rec_a1_var = tk.StringVar(); ttk.Entry(sec_q_frame, textvariable=self.rec_a1_var, show='*').grid(row=1, column=0, columnspan=2, sticky='ew', padx=10, pady=5)
        self.rec_q2_label = ttk.Label(sec_q_frame, text="Q2:"); self.rec_q2_label.grid(row=2, column=0, columnspan=2, sticky='w', padx=10, pady=5)
        self.rec_a2_var = tk.StringVar(); ttk.Entry(sec_q_frame, textvariable=self.rec_a2_var, show='*').grid(row=3, column=0, columnspan=2, sticky='ew', padx=10, pady=5)
        ttk.Button(content, text="Verify Answers", command=self.verify_recovery_answers).pack(pady=20)
        ttk.Button(content, text="< Back to Login", command=self.logout).pack(pady=5)
        return frame

    def create_recovery_reset_frame(self):
        frame, content = self.create_centered_frame()
        ttk.Label(content, text="Reset Your Password", style='Title.TLabel').pack(pady=(0, 20))
        reset_frame = ttk.Labelframe(content, text="Enter New Password", style='TLabelframe')
        reset_frame.pack(pady=10, padx=20, fill="x")
        self.reset_pass_var = tk.StringVar()
        ttk.Entry(reset_frame, textvariable=self.reset_pass_var, show='*', width=40, font=FONT_NORMAL).pack(pady=15, padx=15)
        ttk.Button(content, text="Save New Password", command=self.perform_password_reset).pack(pady=10)
        return frame

    # --- Application Flow & Logic ---
    def show_frame(self, frame_name):
        self.stop_camera()
        if frame_name == 'register':
            self.reg_credentials_frame.pack(pady=20); self.reg_face_frame.pack_forget(); self.reg_security_frame.pack_forget()
            self.back_to_login_btn.pack(pady=20, side=tk.BOTTOM)
        for name, frame in self.frames.items():
            if name == frame_name: frame.grid(row=0, column=0, sticky="nsew")
            else: frame.grid_forget()

    def stop_camera(self):
        if self.cap is not None: self.cap.release(); self.cap = None

    def start_camera(self, update_callback):
        self.stop_camera()
        try:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened(): raise Exception("Could not open camera")
            update_callback()
        except Exception as e: messagebox.showerror("Camera Error", f"Failed to start camera: {str(e)}")

    def login_success(self, username):
        self.stop_camera(); self.current_user = username
        self.user_label.config(text=f"Logged in as: {username}")
        self.refresh_file_list(); self.show_frame('file_explorer')

    def logout(self):
        self.stop_camera(); self.current_user = None; self.login_user_var.set(""); self.pass_login_var.set("")
        self.login_attempt_user = None; self.verification_state = "SEARCHING"; self.match_streak = 0; self.reject_streak = 0; self.blink_counter = 0
        if hasattr(self, 'reg_credentials_frame'):
            self.reg_credentials_frame.pack_forget(); self.reg_face_frame.pack_forget(); self.reg_security_frame.pack_forget()
        self.show_frame('login_user')

    # --- Login Flow ---
    def start_face_login(self):
        username = self.login_user_var.get()
        if not username: messagebox.showerror("Error", "Please enter a username."); return
        if username not in self.users: messagebox.showerror("Error", "Username not found."); return
        self.login_attempt_user = username; self.verification_state = "SEARCHING"; self.match_streak = 0; self.reject_streak = 0; self.blink_counter = 0
        self.show_frame('face_verification'); self.start_camera(self.update_face_verification_camera)

    def update_face_verification_camera(self):
        if self.cap is None: return
        ret, frame = self.cap.read()
        if not ret:
            if self.root.winfo_exists(): self.root.after(10, self.update_face_verification_camera)
            return
            
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(frame_rgb)

        # --- THE DEFINITIVE, ROBUST LOGIC ---
        if not face_locations:
            self.verification_state = "SEARCHING"
            self.match_streak = 0
            self.reject_streak = 0
        else: # A face has been found
            if self.verification_state == "SEARCHING":
                self.verification_state = "CONFIRMING"

            elif self.verification_state == "CONFIRMING":
                current_encodings = face_recognition.face_encodings(frame_rgb, face_locations)
                if not current_encodings: # Handle case where encoding fails
                    self.verification_state = "SEARCHING"; return
                
                stored_encodings = np.load(self.users[self.login_attempt_user]['face_data_file'])
                is_match = any(face_recognition.compare_faces(stored_encodings, current_encodings[0], tolerance=0.5))

                if is_match:
                    self.match_streak += 1; self.reject_streak = 0
                    if self.match_streak >= MATCH_STREAK_REQUIRED: self.verification_state = "WAITING_FOR_BLINK"
                else:
                    self.reject_streak += 1; self.match_streak = 0
                    if self.reject_streak >= REJECT_STREAK_REQUIRED:
                        self.face_status_label.config(text="Face Not Recognized. Access Denied.", style='Error.TLabel')
                        self.stop_camera(); self.root.after(2000, self.logout)
                        return
                        
            elif self.verification_state == "WAITING_FOR_BLINK":
                try:
                    face_landmarks = face_recognition.face_landmarks(frame_rgb, face_locations)
                    if not face_landmarks: raise IndexError # Force a safe reset if landmarks aren't found
                    
                    left_eye = face_landmarks[0]['left_eye']
                    right_eye = face_landmarks[0]['right_eye']
                    ear = (self.eye_aspect_ratio(left_eye) + self.eye_aspect_ratio(right_eye)) / 2.0
                    
                    if ear < EYE_AR_THRESH: self.blink_counter += 1
                    else:
                        if self.blink_counter >= EYE_AR_CONSEC_FRAMES: self.verification_state = "VERIFIED"
                        self.blink_counter = 0
                except IndexError:
                    # This is our safety net. If landmarks fail for a frame, we don't crash.
                    # We can optionally reset to searching if this happens too often.
                    self.verification_state = "SEARCHING"

        # Update Status Label based on the current state
        if self.verification_state == "SEARCHING": self.face_status_label.config(style='TLabel', text="Looking for face...")
        elif self.verification_state == "CONFIRMING": self.face_status_label.config(style='TLabel', text="Face Detected. Hold Still...")
        elif self.verification_state == "WAITING_FOR_BLINK": self.face_status_label.config(text="Face Matched. Please Blink.")
        elif self.verification_state == "VERIFIED":
            self.face_status_label.config(text="Success! Logging in...", style='Success.TLabel')
            self.stop_camera(); self.root.after(1500, lambda: self.login_success(self.login_attempt_user))
            return

        # Update camera feed and schedule next frame
        photo = ImageTk.PhotoImage(image=Image.fromarray(cv2.resize(frame_rgb, (320, 240))))
        self.face_cam_label.configure(image=photo); self.face_cam_label.image = photo
        if self.root.winfo_exists(): self.root.after(10, self.update_face_verification_camera)

    def show_password_login(self):
        self.stop_camera(); self.show_frame('password_login')
        self.pass_login_user_label.config(text=f"Username: {self.login_attempt_user or 'N/A'}")

    def verify_password_login(self):
        password = self.pass_login_var.get()
        if not password: messagebox.showerror("Error", "Password cannot be empty."); return
        if self.login_attempt_user in self.users and self.verify_value(password, self.users[self.login_attempt_user]['password']):
            self.login_success(self.login_attempt_user)
        else: messagebox.showerror("Error", "Incorrect password.")

    # --- Registration Flow ---
    def start_face_capture_step(self):
        username = self.reg_username_var.get(); password = self.reg_password_var.get()
        if not username or not password: messagebox.showerror("Error", "Username and Password cannot be empty."); return
        if username in self.users: messagebox.showerror("Error", "Username already exists."); return
        self.reg_credentials_frame.pack_forget(); self.reg_face_frame.pack(); self.back_to_login_btn.pack_forget()
        self.reg_capture_step = 0; self.reg_face_encodings = []
        self.update_face_capture_prompt(); self.start_camera(self.update_reg_camera)

    def update_reg_camera(self):
        if self.cap is None: return
        ret, frame = self.cap.read()
        if ret:
            photo = ImageTk.PhotoImage(image=Image.fromarray(cv2.cvtColor(cv2.resize(frame, (320,240)), cv2.COLOR_BGR2RGB)))
            self.reg_cam_label.configure(image=photo); self.reg_cam_label.image = photo
            self.root.after(10, self.update_reg_camera)

    def update_face_capture_prompt(self):
        self.reg_face_prompt_label.config(text=self.reg_capture_prompts[self.reg_capture_step])

    def process_face_capture(self):
        if self.cap is None: return
        ret, frame = self.cap.read()
        if ret:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_frame)
            if not face_locations: messagebox.showerror("Error", "No face detected. Please try again."); return
            encoding = face_recognition.face_encodings(rgb_frame, face_locations)[0]
            self.reg_face_encodings.append(encoding); self.reg_capture_step += 1
            if self.reg_capture_step >= len(self.reg_capture_prompts):
                self.stop_camera(); self.reg_face_frame.pack_forget(); self.reg_security_frame.pack(); self.back_to_login_btn.pack(pady=20, side=tk.BOTTOM)
            else: self.update_face_capture_prompt()

    def complete_registration(self):
        q1 = self.sec_q1_var.get(); a1 = self.sec_a1_var.get(); q2 = self.sec_q2_var.get(); a2 = self.sec_a2_var.get()
        if not all([q1, a1, q2, a2]): messagebox.showerror("Error", "Please fill in all question and answer fields."); return
        if q1.strip() == q2.strip(): messagebox.showerror("Error", "Please provide two different security questions."); return
        username = self.reg_username_var.get(); face_data_file = os.path.join(self.face_data_dir, f"{username}_faces.npy")
        np.save(face_data_file, np.array(self.reg_face_encodings))
        self.users[username] = {"password": self.hash_value(self.reg_password_var.get()), "face_data_file": face_data_file, "security_questions": [{"question": q1.strip(), "answer": self.hash_value(a1.lower().strip())}, {"question": q2.strip(), "answer": self.hash_value(a2.lower().strip())}]}
        self.save_json(self.users_file, self.users); messagebox.showinfo("Success", "Registration successful! You can now log in."); self.logout()

    # --- Account Recovery Flow ---
    def start_recovery_from_login(self, event=None):
        if self.login_attempt_user: self.recovery_user_var.set(self.login_attempt_user)
        else: self.recovery_user_var.set("")
        self.show_frame('recovery_user')

    def verify_recovery_user(self):
        username_to_recover = self.recovery_user_var.get()
        if not username_to_recover: messagebox.showerror("Error", "Please enter a username."); return
        if username_to_recover not in self.users: messagebox.showerror("Error", "Username not found."); return
        self.login_attempt_user = username_to_recover
        user_data = self.users[self.login_attempt_user]
        self.rec_q1_label.config(text=user_data['security_questions'][0]['question'])
        self.rec_q2_label.config(text=user_data['security_questions'][1]['question'])
        self.rec_a1_var.set(""); self.rec_a2_var.set("")
        self.show_frame('recovery_questions')

    def verify_recovery_answers(self):
        a1 = self.rec_a1_var.get().lower().strip(); a2 = self.rec_a2_var.get().lower().strip()
        user_data = self.users[self.login_attempt_user]
        hashed_a1 = user_data['security_questions'][0]['answer']; hashed_a2 = user_data['security_questions'][1]['answer']
        if self.verify_value(a1, hashed_a1) and self.verify_value(a2, hashed_a2): self.show_frame('recovery_reset')
        else: messagebox.showerror("Error", "One or both answers are incorrect.")

    def perform_password_reset(self):
        new_password = self.reset_pass_var.get()
        if not new_password: messagebox.showerror("Error", "Password cannot be empty."); return
        self.users[self.login_attempt_user]['password'] = self.hash_value(new_password)
        self.save_json(self.users_file, self.users)
        messagebox.showinfo("Success", "Your password has been reset successfully. Please log in."); self.logout()
    
    # --- File Management ---
    def upload_file(self):
        filename = filedialog.askopenfilename()
        if filename:
            new_filename = os.path.basename(filename); destination = os.path.join(self.secure_dir, new_filename)
            try:
                shutil.copy2(filename, destination); self.permissions[new_filename] = {"owner": self.current_user, "shared": {}}
                self.save_json(self.permissions_file, self.permissions); self.refresh_file_list(); messagebox.showinfo("Success", "File uploaded successfully")
            except Exception as e: messagebox.showerror("Error", f"Failed to upload file: {str(e)}")

    def download_file(self):
        selected = self.file_tree.selection()
        if not selected: messagebox.showerror("Error", "Please select a file to download"); return
        filename = self.file_tree.item(selected[0])["text"]; source = os.path.join(self.secure_dir, filename)
        destination = filedialog.asksaveasfilename(defaultextension=os.path.splitext(filename)[1], initialfile=filename)
        if destination:
            try: shutil.copy2(source, destination); messagebox.showinfo("Success", "File downloaded successfully")
            except Exception as e: messagebox.showerror("Error", f"Failed to download file: {str(e)}")

    def delete_file(self):
        selected = self.file_tree.selection()
        if not selected: messagebox.showerror("Error", "Please select a file to delete"); return
        filename = self.file_tree.item(selected[0])["text"]
        if self.permissions.get(filename, {}).get("owner") != self.current_user: messagebox.showerror("Error", "You don't have permission to delete this file"); return
        if messagebox.askyesno("Confirm", f"Are you sure you want to delete {filename}?"):
            try:
                os.remove(os.path.join(self.secure_dir, filename))
                if filename in self.permissions: del self.permissions[filename]
                self.save_json(self.permissions_file, self.permissions); self.refresh_file_list(); messagebox.showinfo("Success", "File deleted successfully")
            except Exception as e: messagebox.showerror("Error", f"Failed to delete file: {str(e)}")

    def share_file(self):
        selected = self.file_tree.selection()
        if not selected: messagebox.showerror("Error", "Please select a file to share"); return
        filename = self.file_tree.item(selected[0])["text"]
        if self.permissions.get(filename, {}).get("owner") != self.current_user: messagebox.showerror("Error", "You don't have permission to share this file"); return
        ShareDialog(self.root, filename, list(self.users.keys()), self.permissions, self.save_json, self.permissions_file, self.refresh_file_list)

    def refresh_file_list(self):
        for item in self.file_tree.get_children(): self.file_tree.delete(item)
        if not os.path.exists(self.secure_dir): os.makedirs(self.secure_dir)
        for filename in os.listdir(self.secure_dir):
            file_perms = self.permissions.get(filename, {}); owner = file_perms.get("owner", "Unknown")
            access = "Full" if owner == self.current_user else file_perms.get("shared", {}).get(self.current_user, "None")
            if access != "None": self.file_tree.insert("", tk.END, text=filename, values=(owner, access))

# --- ShareDialog Class ---
class ShareDialog:
    def __init__(self, parent, filename, users, permissions, save_callback, permissions_file, refresh_callback):
        self.dialog = tk.Toplevel(parent); self.dialog.title(f"Share {filename}"); self.dialog.geometry("300x400"); self.dialog.configure(bg=BG_COLOR)
        self.dialog.transient(parent); self.dialog.grab_set()
        self.filename = filename; self.users = users; self.permissions = permissions; self.save_callback = save_callback
        self.permissions_file = permissions_file; self.refresh_callback = refresh_callback; self.setup_gui()
    def setup_gui(self):
        style = ttk.Style(); style.configure('Share.TCheckbutton', background=BG_COLOR, foreground=FG_COLOR, font=FONT_NORMAL)
        ttk.Label(self.dialog, text="Select users to share with:", font=FONT_BOLD).pack(pady=10); self.user_vars = {}
        shared_users = self.permissions.get(self.filename, {}).get("shared", {})
        for user in self.users:
            if user == self.permissions.get(self.filename, {}).get("owner"): continue
            var = tk.BooleanVar(value=user in shared_users); self.user_vars[user] = var
            ttk.Checkbutton(self.dialog, text=user, variable=var, style='Share.TCheckbutton').pack(anchor=tk.W, padx=20)
        ttk.Button(self.dialog, text="Save", command=self.save_shares).pack(pady=20)
    def save_shares(self):
        self.permissions[self.filename]["shared"] = {user: "Read" for user, var in self.user_vars.items() if var.get()}
        self.save_callback(self.permissions_file, self.permissions); self.refresh_callback(); self.dialog.destroy()

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = SecureFileExplorer(root)
        root.mainloop()
    except Exception as e:
        error_msg = f"A fatal error occurred:\n{str(e)}\n\n{traceback.format_exc()}"
        messagebox.showerror("Fatal Error", error_msg)
        sys.exit(1)
