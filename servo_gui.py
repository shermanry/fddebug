#!/usr/bin/env python3
"""
Feetech Servo Control GUI
macOS compatible - uses Canvas for color indicators
"""

import tkinter as tk
from tkinter import ttk, messagebox
import serial.tools.list_ports
from typing import Optional, List
from feetech_servo import FeetechServo, SCSReg
import os

os.environ['TK_SILENCE_DEPRECATION'] = '1'


class ServoController:
    def __init__(self):
        self.servo: Optional[FeetechServo] = None
        self.port: Optional[str] = None
    
    def connect(self, port: str, baudrate: int = 1000000) -> bool:
        self.disconnect()
        self.servo = FeetechServo()
        if self.servo.open(port, baudrate):
            self.port = port
            return True
        self.servo = None
        return False
    
    def disconnect(self):
        if self.servo:
            self.servo.close()
            self.servo = None
            self.port = None


class ServoCard(tk.LabelFrame):
    """Servo control card using LabelFrame for proper rendering"""
    
    def __init__(self, master, index: int, controller: ServoController):
        super().__init__(master, text=f" Servo {index + 1} ", 
                        font=('Helvetica', 11, 'bold'),
                        labelanchor='n', padx=6, pady=4)
        
        self.index = index
        self.controller = controller
        self.servo_id: Optional[int] = None
        self.connected = False
        self.position = 512
        self.min_pos = 0
        self.max_pos = 1023
        
        self._create_widgets()
    
    def _create_widgets(self):
        # Status indicator (Canvas circle)
        top_row = tk.Frame(self)
        top_row.pack(fill='x', pady=2)
        
        self.status_canvas = tk.Canvas(top_row, width=16, height=16, 
                                       highlightthickness=0, bg=self.cget('bg'))
        self.status_canvas.pack(side='left')
        self.status_circle = self.status_canvas.create_oval(2, 2, 14, 14, 
                                                            fill='gray', outline='darkgray')
        
        # ID entry
        tk.Label(top_row, text="ID:").pack(side='left', padx=(8, 2))
        
        self.id_var = tk.StringVar(value="1")
        self.id_spin = tk.Spinbox(top_row, from_=1, to=253, width=4,
                                  textvariable=self.id_var)
        self.id_spin.pack(side='left')
        
        self.scan_btn = tk.Button(top_row, text="Connect", width=7,
                                 command=self._scan_and_connect)
        self.scan_btn.pack(side='right')
        
        # Position display
        pos_frame = tk.Frame(self)
        pos_frame.pack(fill='x', pady=6)
        
        self.pos_var = tk.StringVar(value="---")
        self.pos_label = tk.Label(pos_frame, textvariable=self.pos_var,
                                 font=('Courier', 24, 'bold'))
        self.pos_label.pack()
        
        self.angle_var = tk.StringVar(value="--°")
        tk.Label(pos_frame, textvariable=self.angle_var, 
                font=('Helvetica', 10)).pack()
        
        # Slider
        slider_frame = tk.Frame(self)
        slider_frame.pack(fill='x', pady=2)
        
        self.min_label = tk.Label(slider_frame, text="0", font=('Helvetica', 8), width=4)
        self.min_label.pack(side='left')
        
        self.slider = tk.Scale(slider_frame, from_=0, to=1023, orient='horizontal',
                              command=self._on_slider, showvalue=False, length=130)
        self.slider.set(512)
        self.slider.pack(side='left', fill='x', expand=True)
        
        self.max_label = tk.Label(slider_frame, text="1023", font=('Helvetica', 8), width=4)
        self.max_label.pack(side='right')
        
        # Quick buttons
        btn_frame = tk.Frame(self)
        btn_frame.pack(fill='x', pady=4)
        
        for pos, label in [(0, "Min"), (512, "Mid"), (1023, "Max")]:
            tk.Button(btn_frame, text=label, width=5,
                     command=lambda p=pos: self._goto(p)).pack(side='left', expand=True)
        
        # Status info
        info_frame = tk.Frame(self)
        info_frame.pack(fill='x', pady=2)
        
        self.voltage_var = tk.StringVar(value="--V")
        tk.Label(info_frame, textvariable=self.voltage_var, 
                font=('Helvetica', 9)).pack(side='left', expand=True)
        
        self.temp_var = tk.StringVar(value="--°C")
        tk.Label(info_frame, textvariable=self.temp_var,
                font=('Helvetica', 9)).pack(side='left', expand=True)
        
        self.load_var = tk.StringVar(value="--%")
        tk.Label(info_frame, textvariable=self.load_var,
                font=('Helvetica', 9)).pack(side='left', expand=True)
    
    def _scan_and_connect(self):
        if not self.controller.servo:
            messagebox.showwarning("Not Connected", "Connect to port first")
            return
        
        try:
            servo_id = int(self.id_var.get())
        except:
            return
        
        self.scan_btn.configure(text="...", state='disabled')
        self.update_idletasks()
        
        result = self.controller.servo.ping(servo_id)
        
        self.scan_btn.configure(state='normal')
        
        if result >= 0:
            self.servo_id = servo_id
            self.connected = True
            self._set_connected()
            self._read_info()
        else:
            self.scan_btn.configure(text="Not Found")
            self.after(1500, lambda: self.scan_btn.configure(text="Connect"))
    
    def _set_connected(self):
        """Show connected state"""
        # Green circle
        self.status_canvas.itemconfig(self.status_circle, fill='#00cc66', outline='#00aa44')
        # Update button
        self.scan_btn.configure(text="✓ OK")
        # Update label frame title
        self.configure(text=f" Servo {self.index + 1} [ID:{self.servo_id}] ", 
                      fg='#006633')
    
    def _set_disconnected(self):
        """Reset to disconnected state"""
        self.status_canvas.itemconfig(self.status_circle, fill='gray', outline='darkgray')
        self.scan_btn.configure(text="Connect")
        self.configure(text=f" Servo {self.index + 1} ", fg='black')
        self.pos_var.set("---")
        self.angle_var.set("--°")
        self.voltage_var.set("--V")
        self.temp_var.set("--°C")
        self.load_var.set("--%")
        self.connected = False
        self.servo_id = None
    
    def _read_info(self):
        if not self.connected or not self.controller.servo:
            return
        
        try:
            min_val = self.controller.servo.read_word(self.servo_id, SCSReg.MIN_ANGLE_LIMIT_L)
            max_val = self.controller.servo.read_word(self.servo_id, SCSReg.MAX_ANGLE_LIMIT_L)
            
            if min_val >= 0:
                self.min_pos = min_val
                self.min_label.configure(text=str(min_val))
            if max_val > 0 and max_val <= 4095:
                self.max_pos = max_val
                self.max_label.configure(text=str(max_val))
            
            self.slider.configure(from_=self.min_pos, to=self.max_pos)
            
            pos = self.controller.servo.read_position(self.servo_id)
            if pos >= 0:
                self.position = pos
                self.slider.set(pos)
                self.pos_var.set(str(pos))
                angle = (pos / 1023) * 180
                self.angle_var.set(f"{angle:.1f}°")
            
            voltage = self.controller.servo.read_voltage(self.servo_id)
            temp = self.controller.servo.read_temperature(self.servo_id)
            load = self.controller.servo.read_load(self.servo_id)
            
            if voltage >= 0:
                self.voltage_var.set(f"{voltage:.1f}V")
            if temp >= 0:
                self.temp_var.set(f"{temp}°C")
            if load >= 0:
                self.load_var.set(f"{load//10}%")
        except Exception as e:
            print(f"Error: {e}")
    
    def _on_slider(self, value):
        pos = int(float(value))
        self.pos_var.set(str(pos))
        angle = (pos / 1023) * 180
        self.angle_var.set(f"{angle:.1f}°")
        
        if self.connected and self.controller.servo:
            try:
                self.controller.servo.write_position(self.servo_id, pos, speed=1000)
            except:
                pass
    
    def _goto(self, pos):
        pos = max(self.min_pos, min(self.max_pos, pos))
        self.slider.set(pos)
        self._on_slider(pos)
    
    def auto_connect(self, servo_id: int):
        self.id_var.set(str(servo_id))
        self.servo_id = servo_id
        self.connected = True
        self._set_connected()
        self._read_info()
    
    def refresh(self):
        if self.connected:
            self._read_info()


class ServoGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("Feetech Servo Control")
        self.geometry("920x780")
        
        self.controller = ServoController()
        self.cards: List[ServoCard] = []
        
        self._create_widgets()
        self._refresh_ports()
    
    def _create_widgets(self):
        # Header
        header = tk.Frame(self)
        header.pack(fill='x', padx=10, pady=8)
        
        tk.Label(header, text="◈ Feetech Servo Control",
                font=('Helvetica', 18, 'bold')).pack(side='left')
        
        # Connection frame
        conn_frame = tk.LabelFrame(header, text=" Connection ", padx=8, pady=4)
        conn_frame.pack(side='right')
        
        tk.Label(conn_frame, text="Port:").pack(side='left')
        
        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(conn_frame, textvariable=self.port_var, width=18)
        self.port_combo.pack(side='left', padx=4)
        
        tk.Button(conn_frame, text="↻", command=self._refresh_ports).pack(side='left')
        
        self.connect_btn = tk.Button(conn_frame, text="Connect", width=10,
                                    command=self._toggle_connect)
        self.connect_btn.pack(side='left', padx=4)
        
        # Connection status
        self.conn_canvas = tk.Canvas(conn_frame, width=20, height=20, highlightthickness=0)
        self.conn_canvas.pack(side='left', padx=4)
        self.conn_circle = self.conn_canvas.create_oval(4, 4, 18, 18, 
                                                        fill='gray', outline='darkgray')
        
        # Toolbar
        toolbar = tk.Frame(self)
        toolbar.pack(fill='x', padx=10, pady=4)
        
        tk.Button(toolbar, text="🔍 Scan All", command=self._scan_all).pack(side='left', padx=2)
        tk.Button(toolbar, text="📊 Refresh All", command=self._refresh_all).pack(side='left', padx=2)
        tk.Button(toolbar, text="⏹ STOP ALL", fg='red', command=self._stop_all).pack(side='left', padx=2)
        
        # Sync frame
        sync_frame = tk.LabelFrame(toolbar, text=" Sync Move ", padx=4)
        sync_frame.pack(side='right')
        
        for pos, label in [(0, "Min"), (512, "Center"), (1023, "Max")]:
            tk.Button(sync_frame, text=label, width=6,
                     command=lambda p=pos: self._sync_move(p)).pack(side='left', padx=1)
        
        # Grid of servo cards
        grid_frame = tk.Frame(self)
        grid_frame.pack(fill='both', expand=True, padx=10, pady=8)
        
        for row in range(4):
            row_frame = tk.Frame(grid_frame)
            row_frame.pack(fill='both', expand=True, pady=2)
            
            for col in range(4):
                idx = row * 4 + col
                card = ServoCard(row_frame, idx, self.controller)
                card.pack(side='left', fill='both', expand=True, padx=2)
                self.cards.append(card)
        
        # Status bar
        self.status_var = tk.StringVar(value="Ready - Select port and click Connect")
        status_bar = tk.Label(self, textvariable=self.status_var, 
                             anchor='w', relief='sunken', padx=8)
        status_bar.pack(fill='x', side='bottom')
    
    def _refresh_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()
                if 'usbserial' in p.device or 'ttyUSB' in p.device]
        self.port_combo['values'] = ports if ports else ['No ports found']
        if ports:
            self.port_var.set(ports[0])
    
    def _toggle_connect(self):
        if self.controller.servo:
            # Disconnect
            self.controller.disconnect()
            self.connect_btn.configure(text="Connect")
            self.conn_canvas.itemconfig(self.conn_circle, fill='gray', outline='darkgray')
            self.status_var.set("Disconnected")
            for card in self.cards:
                card._set_disconnected()
        else:
            # Connect
            port = self.port_var.get()
            if not port or port == 'No ports found':
                messagebox.showwarning("No Port", "Select a port first")
                return
            
            self.status_var.set(f"Connecting to {port}...")
            self.update_idletasks()
            
            if self.controller.connect(port):
                self.connect_btn.configure(text="Disconnect")
                self.conn_canvas.itemconfig(self.conn_circle, fill='#00cc66', outline='#00aa44')
                self.status_var.set(f"Connected to {port} - Scanning...")
                self.update_idletasks()
                self._scan_all()
            else:
                self.status_var.set(f"Failed to connect to {port}")
                messagebox.showerror("Error", f"Could not open {port}")
    
    def _scan_all(self):
        if not self.controller.servo:
            messagebox.showwarning("Not Connected", "Connect first")
            return
        
        found = []
        for sid in range(1, 21):
            self.status_var.set(f"Scanning ID {sid}...")
            self.update_idletasks()
            try:
                if self.controller.servo.ping(sid) >= 0:
                    found.append(sid)
            except:
                pass
        
        for i, sid in enumerate(found[:16]):
            self.cards[i].auto_connect(sid)
        
        if found:
            self.status_var.set(f"✓ Found {len(found)} servo(s): {found}")
        else:
            self.status_var.set("No servos found - check wiring and power")
    
    def _refresh_all(self):
        for card in self.cards:
            card.refresh()
        self.status_var.set("Status refreshed")
    
    def _stop_all(self):
        if not self.controller.servo:
            return
        for card in self.cards:
            if card.connected and card.servo_id:
                try:
                    self.controller.servo.enable_torque(card.servo_id, False)
                except:
                    pass
        self.status_var.set("⚠ STOPPED - Torque disabled on all servos")
    
    def _sync_move(self, pos: int):
        if not self.controller.servo:
            return
        for card in self.cards:
            if card.connected:
                card._goto(pos)
        self.status_var.set(f"Sync move to position {pos}")


if __name__ == '__main__':
    ServoGUI().mainloop()
