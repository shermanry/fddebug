#!/usr/bin/env python3
"""
Feetech Servo Control - Web Interface
Beautiful dark theme with programming features
"""

from flask import Flask, render_template_string, jsonify, request
import serial.tools.list_ports
import os
import sys
import glob
from feetech_servo import FeetechServo, BaudRate, get_servo_type, SCSType, STSType, HLSType
import threading
import time
from collections import defaultdict

app = Flask(__name__)

# Global servo controller
controller = {
    'servo': None,
    'port': None,
    'baudrate': 1000000,
    'connected_servos': {},  # card_idx -> servo_id
    'servo_types': {}  # servo_id -> 'scs', 'sts', or 'hls'
}
lock = threading.Lock()

# Step queue to prevent drift when spamming commands
step_queues = defaultdict(list)

def process_step_queues():
    while True:
        time.sleep(0.05)
        with lock:
            if not controller['servo']: continue
            for servo_id, queue in list(step_queues.items()):
                if not queue: continue
                
                try:
                    servo = controller['servo']
                    servo.configure_for_type(controller['servo_types'].get(servo_id, 'sts'))
                    # Check if currently moving
                    if not servo.is_moving(servo_id):
                        steps = sum(queue)
                        queue.clear()
                        if steps != 0:
                            servo.write_step(servo_id, steps)
                except Exception:
                    pass

threading.Thread(target=process_step_queues, daemon=True).start()

def detect_servo_type(servo, servo_id):
    """Detect if servo is SCS or STS using the library's detect_type method"""
    return servo.detect_type(servo_id)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Feetech Servo Control</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, #0a0a12 0%, #1a1a2e 100%);
            color: #e0e0e0;
            min-height: 100vh;
        }
        
        .header {
            background: rgba(20, 20, 35, 0.9);
            backdrop-filter: blur(10px);
            padding: 16px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #2a2a4a;
            position: sticky;
            top: 0;
            z-index: 100;
        }
        
        .logo { font-size: 24px; font-weight: 700; color: #00ddaa; }
        .logo span { color: #888; font-weight: 400; }
        
        .connection {
            display: flex;
            align-items: center;
            gap: 12px;
            background: rgba(40, 40, 60, 0.6);
            padding: 8px 16px;
            border-radius: 12px;
        }
        
        .status-dot {
            width: 12px; height: 12px;
            border-radius: 50%;
            background: #666;
            transition: all 0.3s;
        }
        .status-dot.connected {
            background: #00dd88;
            box-shadow: 0 0 12px #00dd88;
        }
        
        select, button, input {
            background: #2a2a4a;
            color: #e0e0e0;
            border: 1px solid #3a3a5a;
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.2s;
        }
        select:hover, button:hover { border-color: #00ddaa; }
        input:focus { border-color: #00ddaa; outline: none; }
        
        button.primary {
            background: linear-gradient(135deg, #00ddaa 0%, #00aa88 100%);
            color: #0a0a12;
            font-weight: 600;
            border: none;
        }
        button.primary:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 20px rgba(0, 221, 170, 0.3);
        }
        button.danger {
            background: linear-gradient(135deg, #ff4466 0%, #cc3355 100%);
            color: white;
            border: none;
        }
        button.warning {
            background: linear-gradient(135deg, #ffaa00 0%, #dd8800 100%);
            color: #0a0a12;
            border: none;
        }
        
        .toolbar {
            padding: 16px 24px;
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
        }
        .toolbar-group {
            display: flex;
            gap: 8px;
            background: rgba(30, 30, 50, 0.5);
            padding: 8px 12px;
            border-radius: 10px;
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 16px;
            padding: 0 24px 24px;
        }
        @media (max-width: 1200px) { .grid { grid-template-columns: repeat(3, 1fr); } }
        @media (max-width: 900px) { .grid { grid-template-columns: repeat(2, 1fr); } }
        @media (max-width: 600px) { .grid { grid-template-columns: 1fr; } }
        
        .card {
            background: linear-gradient(145deg, #1e1e32 0%, #15152a 100%);
            border-radius: 16px;
            padding: 20px;
            border: 1px solid #2a2a4a;
            transition: all 0.3s;
        }
        .card:hover {
            border-color: #3a3a6a;
            transform: translateY(-2px);
        }
        .card.connected {
            border-color: #00aa88;
            box-shadow: 0 0 30px rgba(0, 170, 130, 0.15);
        }
        
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }
        .card-title {
            font-size: 13px;
            font-weight: 600;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .card.connected .card-title { color: #00ddaa; }

        .type-badge {
            display: none;
            font-size: 11px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 6px;
            cursor: pointer;
            letter-spacing: 0.5px;
            border: 1px solid transparent;
            transition: all 0.2s;
            user-select: none;
        }
        .type-badge:hover {
            filter: brightness(1.3);
            border-color: rgba(255,255,255,0.2);
        }
        .type-badge.scs { background: #1a3a2a; color: #44cc88; }
        .type-badge.sts { background: #1a2a3a; color: #4488cc; }
        .type-badge.hls { background: #2a1a3a; color: #aa66dd; }

        .card-status {
            width: 10px; height: 10px;
            border-radius: 50%;
            background: #444;
        }
        .card.connected .card-status {
            background: #00dd88;
            box-shadow: 0 0 8px #00dd88;
        }
        
        .id-row {
            display: flex;
            gap: 8px;
            margin-bottom: 16px;
        }
        .id-input {
            width: 60px;
            background: #252540;
            border: 1px solid #3a3a5a;
            color: #e0e0e0;
            padding: 6px 10px;
            border-radius: 6px;
            font-size: 14px;
        }
        
        .position-display { text-align: center; margin: 20px 0; }
        .position-input {
            font-family: 'SF Mono', 'Menlo', monospace;
            font-size: 36px;
            font-weight: 700;
            color: #555;
            background: transparent;
            border: none;
            border-bottom: 2px solid transparent;
            text-align: center;
            width: 100%;
            outline: none;
            transition: all 0.2s;
        }
        .position-input:focus {
            border-bottom-color: #00ddaa;
            color: #00ddaa;
        }
        .card.connected .position-input {
            color: #00ddaa;
            text-shadow: 0 0 20px rgba(0, 221, 170, 0.3);
        }
        .position-input::-webkit-inner-spin-button,
        .position-input::-webkit-outer-spin-button {
            -webkit-appearance: none;
            margin: 0;
        }
        .position-angle {
            font-size: 14px;
            color: #666;
            margin-top: 4px;
        }
        
        .slider-container { margin: 16px 0; }
        .slider-labels {
            display: flex;
            justify-content: space-between;
            font-size: 11px;
            color: #555;
            margin-bottom: 4px;
        }
        .slider {
            width: 100%;
            height: 8px;
            -webkit-appearance: none;
            background: #252540;
            border-radius: 4px;
            outline: none;
        }
        .slider::-webkit-slider-thumb {
            -webkit-appearance: none;
            width: 20px; height: 20px;
            background: linear-gradient(135deg, #00ddaa 0%, #00aa88 100%);
            border-radius: 50%;
            cursor: pointer;
            box-shadow: 0 2px 10px rgba(0, 221, 170, 0.4);
        }
        
        .quick-buttons {
            display: flex;
            gap: 6px;
            margin: 12px 0;
        }
        .quick-btn {
            flex: 1;
            padding: 8px;
            background: #252540;
            border: 1px solid #3a3a5a;
            color: #888;
            border-radius: 6px;
            font-size: 12px;
        }
        .quick-btn:hover {
            background: #00aa88;
            color: #0a0a12;
            border-color: #00aa88;
        }
        
        .status-row {
            display: flex;
            justify-content: space-around;
            padding: 12px;
            background: rgba(20, 20, 35, 0.5);
            border-radius: 8px;
            margin-top: 12px;
        }
        .status-item { text-align: center; }
        .status-value {
            font-family: 'SF Mono', monospace;
            font-size: 14px;
            color: #888;
        }
        .status-label {
            font-size: 10px;
            color: #555;
            text-transform: uppercase;
        }
        
        .connect-btn {
            font-size: 12px;
            padding: 6px 12px;
            min-width: 80px;
            transition: all 0.3s;
        }
        .connect-btn.success {
            background: linear-gradient(135deg, #00dd88 0%, #00aa66 100%);
            color: #0a0a12;
            border-color: #00dd88;
        }
        .connect-btn.error {
            background: linear-gradient(135deg, #ff4466 0%, #cc3355 100%);
            color: white;
            border-color: #ff4466;
            animation: shake 0.5s;
        }
        @keyframes shake {
            0%, 100% { transform: translateX(0); }
            25% { transform: translateX(-5px); }
            75% { transform: translateX(5px); }
        }
        
        .torque-btn {
            width: 100%;
            margin-top: 8px;
            padding: 8px;
            border: none;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        .torque-btn.on {
            background: linear-gradient(135deg, #00cc77 0%, #00aa55 100%);
            color: white;
            box-shadow: 0 2px 8px rgba(0, 200, 100, 0.3);
        }
        .torque-btn.off {
            background: linear-gradient(135deg, #ff5566 0%, #cc3344 100%);
            color: white;
            box-shadow: 0 2px 8px rgba(255, 80, 100, 0.3);
        }
        .torque-btn:hover {
            transform: scale(1.02);
            filter: brightness(1.1);
        }
        .torque-btn:disabled {
            background: #333;
            color: #666;
            cursor: not-allowed;
            transform: none;
            filter: none;
            box-shadow: none;
        }
        
        .program-btn {
            width: 100%;
            margin-top: 10px;
            background: #352540;
            border-color: #553a5a;
            color: #bb88cc;
        }
        .program-btn:hover {
            background: #8855aa;
            color: white;
            border-color: #8855aa;
        }
        
        /* Step Mode Controls */
        .step-controls {
            display: none;
            background: linear-gradient(145deg, #1a2a3a 0%, #152030 100%);
            border-radius: 10px;
            padding: 12px;
            margin-top: 10px;
            border: 1px solid #2a4a6a;
        }
        .step-controls.active { display: block; }
        
        .step-label {
            font-size: 11px;
            color: #6ab0ff;
            font-weight: 600;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        .step-buttons {
            display: flex;
            gap: 6px;
            margin-bottom: 8px;
        }
        
        .step-btn {
            flex: 1;
            padding: 10px 8px;
            border: none;
            border-radius: 8px;
            font-weight: 700;
            font-size: 14px;
            cursor: pointer;
            transition: all 0.15s;
        }
        .step-btn.back {
            background: linear-gradient(135deg, #ff6644 0%, #cc4422 100%);
            color: white;
        }
        .step-btn.fwd {
            background: linear-gradient(135deg, #44cc66 0%, #22aa44 100%);
            color: white;
        }
        .step-btn:hover {
            transform: scale(1.05);
            filter: brightness(1.15);
        }
        .step-btn:active {
            transform: scale(0.95);
        }
        
        .step-size-row {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .step-size-label {
            font-size: 11px;
            color: #888;
        }
        
        .step-size-input {
            flex: 1;
            padding: 6px 10px;
            background: #1a2a3a;
            border: 1px solid #3a5a7a;
            border-radius: 6px;
            color: #fff;
            font-size: 13px;
            text-align: center;
        }
        
        .step-mode-toggle {
            display: none;  /* Hidden by default, shown for STS servos */
            width: 100%;
            margin-top: 8px;
            padding: 8px;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid #3a5a7a;
            background: #1a2a3a;
            color: #6ab0ff;
        }
        .step-mode-toggle:hover {
            background: #2a4a6a;
            border-color: #4a7aaa;
        }
        .step-mode-toggle.active {
            background: linear-gradient(135deg, #2266aa 0%, #1155aa 100%);
            color: white;
            border-color: #3388cc;
        }
        
        .footer {
            text-align: center;
            padding: 20px;
            color: #444;
            font-size: 12px;
        }
        
        /* Modal */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0; left: 0;
            width: 100%; height: 100%;
            background: rgba(0, 0, 0, 0.8);
            z-index: 1000;
            justify-content: center;
            align-items: center;
        }
        .modal-overlay.active { display: flex; }
        
        .modal {
            background: linear-gradient(145deg, #1e1e32 0%, #15152a 100%);
            border-radius: 20px;
            padding: 24px;
            width: 500px;
            max-width: 90vw;
            max-height: 90vh;
            overflow-y: auto;
            border: 1px solid #3a3a5a;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
        }
        
        .modal-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 1px solid #3a3a5a;
        }
        .modal-title {
            font-size: 20px;
            font-weight: 700;
            color: #bb88cc;
        }
        .modal-close {
            background: none;
            border: none;
            color: #666;
            font-size: 24px;
            cursor: pointer;
            padding: 0;
        }
        .modal-close:hover { color: #ff4466; }
        
        .form-section {
            margin-bottom: 20px;
        }
        .form-section-title {
            font-size: 12px;
            font-weight: 600;
            color: #00ddaa;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 12px;
        }
        
        .form-row {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }
        .form-label {
            width: 120px;
            font-size: 14px;
            color: #888;
        }
        .form-input {
            flex: 1;
            background: #252540;
            border: 1px solid #3a3a5a;
            color: #e0e0e0;
            padding: 10px 12px;
            border-radius: 8px;
            font-size: 14px;
        }
        .form-input:focus {
            border-color: #00ddaa;
            outline: none;
        }
        .form-input::placeholder { color: #555; }
        
        .form-select {
            flex: 1;
            background: #252540;
            border: 1px solid #3a3a5a;
            color: #e0e0e0;
            padding: 10px 12px;
            border-radius: 8px;
            font-size: 14px;
        }
        
        .form-buttons {
            display: flex;
            gap: 12px;
            margin-top: 24px;
            padding-top: 16px;
            border-top: 1px solid #3a3a5a;
        }
        .form-buttons button { flex: 1; padding: 12px; }
        
        .warning-text {
            background: rgba(255, 170, 0, 0.1);
            border: 1px solid rgba(255, 170, 0, 0.3);
            color: #ffaa00;
            padding: 12px;
            border-radius: 8px;
            font-size: 13px;
            margin-bottom: 16px;
        }
        
        .current-value {
            font-family: 'SF Mono', monospace;
            color: #00ddaa;
            font-size: 12px;
        }
        
        .read-btn {
            padding: 6px 12px;
            font-size: 12px;
            margin-left: 8px;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="logo">◈ FEETECH <span>Servo Control</span></div>
        <div class="connection">
            <div class="status-dot" id="connDot"></div>
            <select id="portSelect" onchange="onPortSelectChange()" title="Select Serial Port / UART Interface">
                <option value="">Select Port...</option>
            </select>
            <input type="text" id="customPortInput" placeholder="/dev/serial0" title="Custom port path (e.g. /dev/serial0, /dev/ttyAMA0)" style="display:none; padding: 6px 10px; background: rgba(30,30,45,0.8); border: 1px solid rgba(255,255,255,0.2); border-radius: 8px; color: #fff; width: 140px; font-size: 13px;">
            <select id="baudSelect" title="Communication Baud Rate" style="width: 105px; font-size: 12px; padding: 6px 8px;">
                <option value="1000000" selected>1M baud</option>
                <option value="500000">500K baud</option>
                <option value="250000">250K baud</option>
                <option value="115200">115.2K</option>
                <option value="57600">57.6K</option>
                <option value="38400">38.4K</option>
            </select>
            <button class="primary" id="connectBtn" onclick="toggleConnect()">Connect</button>
        </div>
    </div>
    
    <div class="toolbar">
        <div class="toolbar-group">
            <button onclick="scanAll()">🔍 Scan All</button>
            <button onclick="refreshAll()">📊 Refresh</button>
            <button class="danger" onclick="stopAll()">⏹ STOP ALL</button>
            <button onclick="showAllLimits()">📏 Show Limits</button>
        </div>
        <div class="toolbar-group" style="margin-left: auto;">
            <span style="color: #666; padding: 8px;">Sync:</span>
            <button onclick="syncMove(0)">MIN</button>
            <button onclick="syncMove(512)">CENTER</button>
            <button onclick="syncMove(1023)">MAX</button>
        </div>
    </div>
    
    <div class="grid" id="servoGrid"></div>
    
    <div class="footer">
        <span id="statusText">Ready - Select port and connect</span>
    </div>

    <!-- Programming Modal -->
    <div class="modal-overlay" id="programModal">
        <div class="modal">
            <div class="modal-header">
                <div class="modal-title">⚙️ Program Servo <span id="modalServoId"></span></div>
                <button class="modal-close" onclick="closeModal()">&times;</button>
            </div>
            
            <div class="warning-text">
                ⚠️ Changing ID or baud rate requires power cycle. Be careful!
            </div>
            
            <div class="form-section">
                <div class="form-section-title">Identity</div>
                
                <div class="form-row">
                    <span class="form-label">Current ID:</span>
                    <span class="current-value" id="currentId">--</span>
                </div>
                <div class="form-row">
                    <span class="form-label">New ID:</span>
                    <input type="number" class="form-input" id="newId" min="1" max="253" placeholder="1-253">
                    <button class="warning" onclick="changeId()">Change</button>
                </div>
            </div>
            
            <div class="form-section sts-only">
                <div class="form-section-title">Operating Mode</div>
                
                <div class="form-row">
                    <span class="form-label">Current Mode:</span>
                    <span class="current-value" id="currentMode">--</span>
                    <button class="read-btn" onclick="readMode()">Read</button>
                </div>
                <div class="form-row">
                    <span class="form-label">Set Mode:</span>
                    <select class="form-select" id="newMode">
                        <option value="0">Position Control (Servo)</option>
                        <option value="1">Wheel Mode (Continuous)</option>
                        <option value="2">PWM Mode</option>
                        <option value="3">Multi-turn Mode</option>
                    </select>
                    <button class="primary" onclick="changeMode()">Set</button>
                </div>
            </div>
            
            <div class="form-section">
                <div class="form-section-title">Angle Limits</div>
                
                <div class="form-row">
                    <span class="form-label">Min Limit:</span>
                    <input type="number" class="form-input" id="minLimit" min="-32767" max="32767" placeholder="0">
                    <button class="primary" onclick="setMinLimit()">Set</button>
                </div>
                <div class="form-row">
                    <span class="form-label">Max Limit:</span>
                    <input type="number" class="form-input" id="maxLimit" min="-32767" max="32767" placeholder="4095">
                    <button class="primary" onclick="setMaxLimit()">Set</button>
                </div>
            </div>
            
            <div class="form-section">
                <div class="form-section-title">Baud Rate</div>
                
                <div class="form-row">
                    <span class="form-label">Current:</span>
                    <span class="current-value" id="currentBaud">--</span>
                    <button class="read-btn" onclick="readBaud()">Read</button>
                </div>
                <div class="form-row">
                    <span class="form-label">Set Baud:</span>
                    <select class="form-select" id="newBaud">
                        <option value="0">1,000,000</option>
                        <option value="1">500,000</option>
                        <option value="2">250,000</option>
                        <option value="3">128,000</option>
                        <option value="4">115,200</option>
                        <option value="5">76,800</option>
                        <option value="6">57,600</option>
                        <option value="7">38,400</option>
                    </select>
                    <button class="warning" onclick="changeBaud()">Change</button>
                </div>
            </div>
            
            <div class="form-section">
                <div class="form-section-title">Dead Zone (Compliance)</div>
                
                <div class="form-row">
                    <span class="form-label">CW Dead:</span>
                    <input type="number" class="form-input" id="cwDead" min="0" max="255" placeholder="0">
                    <button class="primary" onclick="setCwDead()">Set</button>
                </div>
                <div class="form-row">
                    <span class="form-label">CCW Dead:</span>
                    <input type="number" class="form-input" id="ccwDead" min="0" max="255" placeholder="0">
                    <button class="primary" onclick="setCcwDead()">Set</button>
                </div>
            </div>
            
            <div class="form-section sts-only">
                <div class="form-section-title">Position Offset</div>
                
                <div class="form-row">
                    <span class="form-label">Offset:</span>
                    <input type="number" class="form-input" id="offset" min="0" max="4095" placeholder="0">
                    <button class="primary" onclick="setOffset()">Set</button>
                </div>
            </div>
            
            <div class="form-section">
                <div class="form-section-title">PID Control</div>
                
                <div class="form-row">
                    <span class="form-label">P (Proportional):</span>
                    <input type="number" class="form-input" id="pidP" min="0" max="255" placeholder="0-255">
                    <button class="primary" onclick="setPidP()">Set</button>
                </div>
                <div class="form-row">
                    <span class="form-label">I (Integral):</span>
                    <input type="number" class="form-input" id="pidI" min="0" max="255" placeholder="0-255">
                    <button class="primary" onclick="setPidI()">Set</button>
                </div>
                <div class="form-row">
                    <span class="form-label">D (Derivative):</span>
                    <input type="number" class="form-input" id="pidD" min="0" max="255" placeholder="0-255">
                    <button class="primary" onclick="setPidD()">Set</button>
                </div>
            </div>
            
            <div class="form-section">
                <div class="form-section-title">Punch (Startup Force)</div>
                
                <div class="form-row">
                    <span class="form-label">Punch:</span>
                    <input type="number" class="form-input" id="punch" min="0" max="1023" placeholder="0-1023">
                    <button class="primary" onclick="setPunch()">Set</button>
                </div>
                <div class="form-row">
                    <span class="form-label">Max Torque:</span>
                    <input type="number" class="form-input" id="maxTorque" min="0" max="1023" placeholder="0-1023">
                    <button class="primary" onclick="setMaxTorque()">Set</button>
                </div>
            </div>
            
            <div class="form-section">
                <div class="form-section-title">Protection Limits</div>
                
                <div class="form-row">
                    <span class="form-label">Max Temp (°C):</span>
                    <input type="number" class="form-input" id="maxTemp" min="0" max="100" placeholder="50-85">
                    <button class="primary" onclick="setMaxTemp()">Set</button>
                </div>
                <div class="form-row">
                    <span class="form-label">Min Voltage (V):</span>
                    <input type="number" class="form-input" id="minVoltage" min="3" max="12" step="0.1" placeholder="5.0">
                    <button class="primary" onclick="setMinVoltage()">Set</button>
                </div>
                <div class="form-row">
                    <span class="form-label">Max Voltage (V):</span>
                    <input type="number" class="form-input" id="maxVoltage" min="5" max="15" step="0.1" placeholder="8.4">
                    <button class="primary" onclick="setMaxVoltage()">Set</button>
                </div>
            </div>
            
            <div class="form-section">
                <div class="form-section-title" id="overloadSectionTitle">Overload Protection</div>
                
                <div class="form-row">
                    <span class="form-label" id="protectionTorqueLabel">Protection Torque:</span>
                    <input type="number" class="form-input" id="protectionTorque" min="0" max="255" placeholder="0-255">
                    <button class="primary" onclick="setProtectionTorque()">Set</button>
                </div>
                <div class="form-row">
                    <span class="form-label" id="protectionTimeLabel">Protection Time (s):</span>
                    <input type="number" class="form-input" id="protectionTime" min="0" max="255" placeholder="0-255">
                    <button class="primary" onclick="setProtectionTime()">Set</button>
                </div>
                <div class="form-row">
                    <span class="form-label">Overload Current:</span>
                    <input type="number" class="form-input" id="protectionCurrent" min="0" max="1023" placeholder="0-1023">
                    <button class="primary" onclick="setProtectionCurrent()">Set</button>
                </div>
            </div>
            
            <div class="form-section">
                <div class="form-section-title">LED & Alarms</div>
                
                <div class="form-row">
                    <span class="form-label">LED Alarm:</span>
                    <select class="form-select" id="ledAlarm">
                        <option value="0">Off</option>
                        <option value="1">Overload</option>
                        <option value="2">Overheat</option>
                        <option value="4">Voltage Error</option>
                        <option value="7">All Alarms</option>
                    </select>
                    <button class="primary" onclick="setLedAlarm()">Set</button>
                </div>
                <div class="form-row">
                    <span class="form-label">Unloading:</span>
                    <select class="form-select" id="unloading">
                        <option value="0">Hold Position</option>
                        <option value="1">Unload on Error</option>
                        <option value="2">Unload on Boot</option>
                        <option value="3">Both</option>
                    </select>
                    <button class="primary" onclick="setUnloading()">Set</button>
                </div>
            </div>
            
            <div class="form-section sts-only">
                <div class="form-section-title" id="speedLoopTitle">Speed Loop (STS/SMS)</div>
                
                <div class="form-row">
                    <span class="form-label">Speed P:</span>
                    <input type="number" class="form-input" id="speedP" min="0" max="255" placeholder="0-255">
                    <button class="primary" onclick="setSpeedP()">Set</button>
                </div>
                <div class="form-row">
                    <span class="form-label">Speed I:</span>
                    <input type="number" class="form-input" id="speedI" min="0" max="255" placeholder="0-255">
                    <button class="primary" onclick="setSpeedI()">Set</button>
                </div>
                <div class="form-row">
                    <span class="form-label">Acceleration:</span>
                    <input type="number" class="form-input" id="acceleration" min="0" max="254" placeholder="0-254">
                    <button class="primary" onclick="setAcceleration()">Set</button>
                </div>
            </div>
            
            <div class="form-section hls-only" style="display:none">
                <div class="form-section-title">Torque Limit (SRAM)</div>
                
                <div class="form-row">
                    <span class="form-label">Torque Limit:</span>
                    <input type="number" class="form-input" id="torqueLimit" min="0" max="1000" placeholder="0-1000">
                    <button class="primary" onclick="setTorqueLimit()">Set</button>
                </div>
            </div>
            
            <div class="form-section hls-only" style="display:none">
                <div class="form-section-title">Runtime PID (SRAM)</div>
                
                <div class="form-row">
                    <span class="form-label">Kp:</span>
                    <input type="number" class="form-input" id="sramKp" min="0" max="255" placeholder="0-255">
                    <button class="primary" onclick="setSramKp()">Set</button>
                </div>
                <div class="form-row">
                    <span class="form-label">Kd:</span>
                    <input type="number" class="form-input" id="sramKd" min="0" max="255" placeholder="0-255">
                    <button class="primary" onclick="setSramKd()">Set</button>
                </div>
                <div class="form-row">
                    <span class="form-label">Ki:</span>
                    <input type="number" class="form-input" id="sramKi" min="0" max="255" placeholder="0-255">
                    <button class="primary" onclick="setSramKi()">Set</button>
                </div>
            </div>
            
            <div class="form-section hls-only" style="display:none">
                <div class="form-section-title">HLS Identity</div>
                
                <div class="form-row">
                    <span class="form-label">Second ID:</span>
                    <input type="number" class="form-input" id="secondId" min="0" max="253" placeholder="0-253">
                    <button class="primary" onclick="setSecondId()">Set</button>
                </div>
                <div class="form-row">
                    <span class="form-label">Angular Resolution:</span>
                    <input type="number" class="form-input" id="angularRes" min="1" max="255" placeholder="1">
                    <button class="primary" onclick="setAngularRes()">Set</button>
                </div>
            </div>
            
            <div class="form-section">
                <div class="form-section-title">Torque</div>
                
                <div class="form-row">
                    <span class="form-label">Status:</span>
                    <span class="current-value" id="currentTorque">--</span>
                </div>
                <div class="form-row">
                    <span class="form-label">Control:</span>
                    <button class="primary" id="torqueEnableBtn" onclick="setTorque(true)" style="flex:1">Enable</button>
                    <button class="danger" id="torqueDisableBtn" onclick="setTorque(false)" style="flex:1">Disable</button>
                </div>
            </div>
            
            <div class="form-section">
                <div class="form-section-title">EPROM Lock</div>
                <div class="form-row">
                    <span class="form-label">Protection:</span>
                    <button class="primary" onclick="lockEprom()" style="flex:1">🔒 Lock EPROM</button>
                    <button class="warning" onclick="unlockEprom()" style="flex:1">🔓 Unlock EPROM</button>
                </div>
            </div>
            
            <div class="form-buttons">
                <button onclick="readAllSettings()">📖 Read All</button>
                <button onclick="closeModal()">Close</button>
            </div>
        </div>
    </div>

    <script>
        let connected = false;
        let servos = {};
        let currentProgramServo = null;
        let autoRefreshInterval = null;
        
        function createCards() {
            const grid = document.getElementById('servoGrid');
            for (let i = 0; i < 16; i++) {
                grid.innerHTML += `
                    <div class="card" id="card${i}">
                        <div class="card-header">
                            <span class="card-title" id="cardTitle${i}">ID ${i + 1}</span>
                            <span class="type-badge" id="typeBadge${i}" onclick="toggleType(${i})" title="Click to change servo type"></span>
                            <div class="card-status"></div>
                        </div>
                        <div class="id-row" style="display: none;">
                            <input type="number" class="id-input" id="id${i}" value="${i + 1}" min="1" max="253">
                        </div>
                        <div style="display: flex; gap: 8px; margin-bottom: 12px;">
                            <button class="connect-btn" id="connectBtn${i}" onclick="connectServo(${i})" style="flex: 1;">Connect ID ${i + 1}</button>
                            <button class="program-btn" onclick="openProgram(${i})" style="width: auto; padding: 8px; margin: 0;">⚙️</button>
                        </div>
                        <div class="position-display">
                            <input type="number" class="position-input" id="pos${i}" value="0" 
                                   onchange="onPositionInput(${i}, this.value)" 
                                   onkeydown="if(event.key==='Enter')onPositionInput(${i}, this.value)">
                            <div class="position-angle" id="angle${i}">--°</div>
                        </div>
                        <div class="slider-container">
                            <div class="slider-labels">
                                <span id="min${i}">0</span>
                                <span id="max${i}">1023</span>
                            </div>
                            <input type="range" class="slider" id="slider${i}" min="0" max="1023" value="512"
                                   oninput="onSlider(${i}, this.value)">
                        </div>
                        <div class="quick-buttons" id="quickBtns${i}">
                            <button class="quick-btn" onclick="gotoPos(${i}, 'min')">MIN</button>
                            <button class="quick-btn" onclick="gotoPos(${i}, 'mid')">MID</button>
                            <button class="quick-btn" onclick="gotoPos(${i}, 'max')">MAX</button>
                        </div>
                        <div class="reg-step-controls" id="regStepControls${i}" style="margin-top: 10px;">
                            <div class="step-buttons">
                                <button class="step-btn back" onclick="doRegStep(${i}, -1)">◀ Step</button>
                                <div class="step-size-row" style="flex: 1; display: flex; justify-content: center; margin: 0 4px;">
                                    <input type="number" class="step-size-input" id="regStepSize${i}" value="10" min="1" max="4095" style="width: 100%; font-size: 11px;">
                                </div>
                                <button class="step-btn fwd" onclick="doRegStep(${i}, 1)">Step ▶</button>
                            </div>
                        </div>
                        <button class="torque-btn" id="torqueBtn${i}" onclick="toggleTorque(${i})">🔒 Torque ON</button>
                        <button class="step-mode-toggle" id="stepToggle${i}" onclick="toggleStepMode(${i})">🔄 Step Mode</button>
                        <div class="step-controls" id="stepControls${i}">
                            <div class="step-label">⚡ Step Mode Active</div>
                            <div class="step-buttons">
                                <button class="step-btn back" onclick="doStep(${i}, -1)">◀ Back</button>
                                <button class="step-btn fwd" onclick="doStep(${i}, 1)">Fwd ▶</button>
                            </div>
                            <div class="step-size-row">
                                <span class="step-size-label">Steps:</span>
                                <input type="number" class="step-size-input" id="stepSize${i}" value="500" min="1" max="10000">
                            </div>
                        </div>
                        <div class="status-row">
                            <div class="status-item">
                                <div class="status-value" id="volt${i}">--</div>
                                <div class="status-label">Volts</div>
                            </div>
                            <div class="status-item">
                                <div class="status-value" id="temp${i}">--</div>
                                <div class="status-label">Temp</div>
                            </div>
                            <div class="status-item">
                                <div class="status-value" id="load${i}">--</div>
                                <div class="status-label">Load</div>
                            </div>
                            <div class="status-item" id="currentItem${i}" style="display:none">
                                <div class="status-value" id="current${i}">--</div>
                                <div class="status-label">Current</div>
                            </div>
                        </div>
                        <button class="program-btn" onclick="openProgram(${i})">⚙️ Program</button>
                    </div>
                `;
            }
        }
        
        function setStatus(text) {
            document.getElementById('statusText').textContent = text;
        }

        function onPortSelectChange() {
            const select = document.getElementById('portSelect');
            const customInput = document.getElementById('customPortInput');
            if (select.value === '__custom__') {
                customInput.style.display = 'inline-block';
                customInput.focus();
            } else {
                customInput.style.display = 'none';
            }
        }
        
        async function loadPorts() {
            try {
                const resp = await fetch('/api/ports?' + new Date().getTime());
                const data = await resp.json();
                console.log("Loaded ports:", data);
                const select = document.getElementById('portSelect');
                select.innerHTML = '<option value="">Select Port...</option>';
                
                const existingDevices = new Set();
                const details = data.details || [];
                
                if (details.length > 0) {
                    details.forEach(p => {
                        existingDevices.add(p.device);
                        const ifaceTag = p.type ? ` [${p.type}]` : '';
                        select.innerHTML += `<option value="${p.device}">${p.device}${ifaceTag}</option>`;
                    });
                    if (data.connected_port) {
                        select.value = data.connected_port;
                    } else {
                        select.value = details[0].device;
                    }
                } else if (data.ports && data.ports.length > 0) {
                    data.ports.forEach(port => {
                        existingDevices.add(port);
                        select.innerHTML += `<option value="${port}">${port}</option>`;
                    });
                    if (data.connected_port) select.value = data.connected_port;
                    else select.value = data.ports[0];
                }

                // Add Raspberry Pi hardware UART presets if not already enumerated
                const rpiPresets = [
                    {device: '/dev/serial0', label: '/dev/serial0 [Pi 4 Primary UART]'},
                    {device: '/dev/ttyAMA0', label: '/dev/ttyAMA0 [Pi 4 PL011 UART]'},
                    {device: '/dev/ttyAMA1', label: '/dev/ttyAMA1 [Pi 4 UART2 / GPIO 0,1]'}
                ];
                let addedPresets = false;
                rpiPresets.forEach(preset => {
                    if (!existingDevices.has(preset.device)) {
                        if (!addedPresets) {
                            select.innerHTML += `<optgroup label="Raspberry Pi Presets">`;
                            addedPresets = true;
                        }
                        select.innerHTML += `<option value="${preset.device}">${preset.label}</option>`;
                    }
                });
                if (addedPresets) {
                    select.innerHTML += `</optgroup>`;
                }

                select.innerHTML += '<option value="__custom__">Custom port path...</option>';

                // If already connected on the server
                if (data.connected && data.connected_port) {
                    connected = true;
                    const btn = document.getElementById('connectBtn');
                    const dot = document.getElementById('connDot');
                    btn.textContent = 'Disconnect';
                    btn.classList.remove('primary');
                    btn.classList.add('danger');
                    dot.classList.add('connected');
                    if (data.connected_baud) {
                        document.getElementById('baudSelect').value = data.connected_baud;
                    }
                    setStatus(`Connected to ${data.connected_port} @ ${(data.connected_baud || 1000000).toLocaleString()} baud`);
                    startAutoRefresh();
                }
            } catch (e) {
                console.error("Failed to load ports:", e);
                alert("Failed to load ports from server. Is it running?");
            }
        }
        
        async function toggleConnect() {
            const btn = document.getElementById('connectBtn');
            const dot = document.getElementById('connDot');
            
            if (connected) {
                stopAutoRefresh();
                await fetch('/api/disconnect', {method: 'POST'});
                connected = false;
                servos = {};
                btn.textContent = 'Connect';
                btn.classList.add('primary');
                btn.classList.remove('danger');
                dot.classList.remove('connected');
                setStatus('Disconnected');
                for (let i = 0; i < 16; i++) {
                    document.getElementById('card' + i).classList.remove('connected');
                    document.getElementById('pos' + i).textContent = '---';
                    document.getElementById('angle' + i).textContent = '--°';
                    document.getElementById('volt' + i).textContent = '--';
                    document.getElementById('temp' + i).textContent = '--';
                    document.getElementById('load' + i).textContent = '--';
                    document.getElementById('current' + i).textContent = '--';
                    document.getElementById('currentItem' + i).style.display = 'none';
                    // Reset connect buttons
                    const connBtn = document.getElementById('connectBtn' + i);
                    const idInput = document.getElementById('id' + i).value;
                    connBtn.textContent = `Connect ID ${idInput}`;
                    connBtn.classList.remove('success', 'error');
                    
                    // Reset card title and type badge
                    document.getElementById('cardTitle' + i).textContent = `ID ${idInput}`;
                    document.getElementById('typeBadge' + i).style.display = 'none';
                }
            } else {
                const portSelect = document.getElementById('portSelect');
                let port = portSelect.value;
                if (port === '__custom__') {
                    port = document.getElementById('customPortInput').value.trim();
                }
                if (!port) { alert('Select or enter a port first'); return; }
                const baud = parseInt(document.getElementById('baudSelect').value) || 1000000;
                setStatus('Connecting to ' + port + '...');
                const resp = await fetch('/api/connect', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({port: port, baudrate: baud})
                });
                const data = await resp.json();
                if (data.success) {
                    connected = true;
                    btn.textContent = 'Disconnect';
                    btn.classList.remove('primary');
                    btn.classList.add('danger');
                    dot.classList.add('connected');
                    setStatus(`Connected to ${port} @ ${baud.toLocaleString()} baud! Scanning...`);
                    scanAll();
                } else {
                    setStatus('Connection failed: ' + (data.error || 'Unknown error'));
                    alert('Could not open port ' + port + ':\n' + (data.error || 'Check wiring/permissions'));
                }
            }
        }
        function showAllLimits() {
            if (!connected) {
                alert("Not connected to any servos.");
                return;
            }
            let msg = "Connected Servos Position Limits:\\n\\n";
            let found = false;
            for (let i = 0; i < 16; i++) {
                if (servos[i]) {
                    const min = document.getElementById('slider' + i).min;
                    const max = document.getElementById('slider' + i).max;
                    const typeLabel = servos[i].type.toUpperCase();
                    msg += `ID ${servos[i].id} (${typeLabel}): Min ${min}, Max ${max}\\n`;
                    found = true;
                }
            }
            if (!found) {
                msg = "No servos are currently connected.";
                alert(msg);
                return;
            }
            
            // Try to copy to clipboard
            if (navigator.clipboard && window.isSecureContext) {
                navigator.clipboard.writeText(msg).then(() => {
                    alert(msg + "\\n\\n(Copied to clipboard!)");
                }).catch(err => {
                    alert(msg);
                });
            } else {
                // Fallback for non-secure contexts (like localhost without https)
                const textArea = document.createElement("textarea");
                textArea.value = msg;
                document.body.appendChild(textArea);
                textArea.focus();
                textArea.select();
                try {
                    document.execCommand('copy');
                    alert(msg + "\\n\\n(Copied to clipboard!)");
                } catch (err) {
                    alert(msg);
                }
                document.body.removeChild(textArea);
            }
        }
        
        async function scanAll() {
            if (!connected) return;
            setStatus('Scanning...');
            const resp = await fetch('/api/scan');
            const data = await resp.json();
            for (let i = 0; i < 16; i++) {
                document.getElementById('card' + i).classList.remove('connected');
            }
            for (let idx = 0; idx < data.found.length && idx < 16; idx++) {
                document.getElementById('id' + idx).value = data.found[idx];
                await connectServo(idx);
            }
            setStatus(`Found ${data.found.length} servo(s): ${data.found.join(', ')}`);
            startAutoRefresh();
        }
        
        async function connectServo(cardIdx) {
            if (!connected) {
                setStatus('Connect to serial port first');
                return;
            }
            
            const btn = document.getElementById('connectBtn' + cardIdx);
            const servoId = parseInt(document.getElementById('id' + cardIdx).value);
            
            // Show loading state
            btn.textContent = '...';
            btn.classList.remove('success', 'error');
            
            try {
                const resp = await fetch('/api/servo/connect', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({card: cardIdx, id: servoId})
                });
                const data = await resp.json();
                
                if (data.success) {
                    // Success - update card title and type badge
                    document.getElementById('card' + cardIdx).classList.add('connected');
                    const servoType = data.type || 'sts';
                    
                    document.getElementById('cardTitle' + cardIdx).textContent = `ID ${servoId}`;
                    updateTypeBadge(cardIdx, servoType);
                    
                    btn.textContent = '✓ Connected';
                    btn.classList.add('success');
                    btn.classList.remove('error');
                    updateCard(cardIdx, data);
                    servos[cardIdx] = {id: servoId, type: servoType};
                    
                    // Show step mode toggle only for STS servos
                    const stepToggle = document.getElementById('stepToggle' + cardIdx);
                    stepToggle.style.display = servoType === 'sts' ? 'block' : 'none';
                    
                    // Show current display for HLS
                    document.getElementById('currentItem' + cardIdx).style.display = servoType === 'hls' ? '' : 'none';

                    startAutoRefresh();
                    setStatus('Connected to ' + servoType.toUpperCase() + ' servo ID ' + servoId);
                } else {
                    // Failed - show error
                    btn.textContent = '✗ Not found';
                    btn.classList.add('error');
                    btn.classList.remove('success');
                    document.getElementById('card' + cardIdx).classList.remove('connected');
                    delete servos[cardIdx];
                    setStatus('No servo found at ID ' + servoId);
                    
                    // Reset button after 2 seconds
                    setTimeout(() => {
                        btn.textContent = `Connect ID ${servoId}`;
                        btn.classList.remove('error');
                    }, 2000);
                }
            } catch (e) {
                btn.textContent = '✗ Error';
                btn.classList.add('error');
                setStatus('Connection error: ' + e.message);
                setTimeout(() => {
                    const idInput = document.getElementById('id' + cardIdx).value;
                    btn.textContent = `Connect ID ${idInput}`;
                    btn.classList.remove('error');
                }, 2000);
            }
        }
        
        function updateTypeBadge(cardIdx, servoType) {
            const badge = document.getElementById('typeBadge' + cardIdx);
            badge.textContent = servoType.toUpperCase();
            badge.className = 'type-badge ' + servoType;
            badge.style.display = 'inline-block';
        }

        async function toggleType(cardIdx) {
            if (!servos[cardIdx]) return;
            const current = servos[cardIdx].type;
            const cycle = {scs: 'sts', sts: 'hls', hls: 'scs'};
            const newType = cycle[current] || 'scs';

            try {
                const resp = await fetch('/api/servo/type', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id: servos[cardIdx].id, type: newType})
                });
                const data = await resp.json();
                if (data.success) {
                    servos[cardIdx].type = newType;
                    updateTypeBadge(cardIdx, newType);
                    const stepToggle = document.getElementById('stepToggle' + cardIdx);
                    stepToggle.style.display = newType === 'sts' ? 'block' : 'none';
                    setStatus(`Servo ${servos[cardIdx].id} type set to ${newType.toUpperCase()}`);
                    updateServo(cardIdx);
                }
            } catch (e) {
                setStatus('Error changing type: ' + e.message);
            }
        }

        function updateCard(idx, data) {
            const pos = data.position;
            const posInput = document.getElementById('pos' + idx);
            
            // Update position input (only if not focused to avoid interrupting user input)
            if (document.activeElement !== posInput) {
                posInput.value = pos != null ? pos : '';
                posInput.placeholder = pos != null ? '' : '---';
            }
            
            // Calculate angle based on servo type
            // SCS: 1024 steps = 300°, STS: 4096 steps = 360°
            if (pos != null) {
                updateAngleDisplay(idx, pos);
            } else {
                document.getElementById('angle' + idx).textContent = '--°';
            }
            
            // Update slider with signed min/max
            const minVal = data.min != null ? data.min : 0;
            const maxVal = data.max != null ? data.max : 4095;
            document.getElementById('min' + idx).textContent = minVal;
            document.getElementById('max' + idx).textContent = maxVal;
            document.getElementById('slider' + idx).min = minVal;
            document.getElementById('slider' + idx).max = maxVal;
            
            if (pos != null) {
                // Clamp position to slider range for display
                const clampedPos = Math.max(minVal, Math.min(maxVal, pos));
                document.getElementById('slider' + idx).value = clampedPos;
            }
            
            document.getElementById('volt' + idx).textContent = data.voltage ? data.voltage.toFixed(1) + 'V' : '--';
            document.getElementById('temp' + idx).textContent = data.temp ? data.temp + '°C' : '--';
            
            // Load: bit 10 is direction, bits 0-9 are magnitude (0-1023 = 0-100%)
            if (data.load != null) {
                const loadMag = data.load & 0x3FF;  // Mask off direction bit
                const loadPct = (loadMag / 1023 * 100).toFixed(0);
                document.getElementById('load' + idx).textContent = loadPct + '%';
            } else {
                document.getElementById('load' + idx).textContent = '--';
            }
            
            // Present Current (HLS only)
            const currentItem = document.getElementById('currentItem' + idx);
            if (servos[idx] && servos[idx].type === 'hls') {
                currentItem.style.display = '';
                if (data.current != null) {
                    document.getElementById('current' + idx).textContent = data.current.toFixed(0) + 'mA';
                } else {
                    document.getElementById('current' + idx).textContent = '--';
                }
            } else {
                currentItem.style.display = 'none';
            }
            
            // Update torque button
            if (data.torque !== undefined) {
                updateTorqueBtn(idx, data.torque);
            }
            
            // Update step mode UI based on current mode
            if (data.mode !== undefined) {
                updateStepModeUI(idx, data.mode);
            }
        }
        
        // Calculate angle based on servo type
        // SCS: 1024 steps = 300° (0-1023)
        // STS: 4096 steps = 360° (0-4095)
        function calcAngle(cardIdx, position) {
            const servo = servos[cardIdx];
            if (!servo) return 0;
            
            if (servo.type === 'scs') {
                // SCS: 1024 steps = 300°
                return (position / 1024 * 300).toFixed(1);
            } else {
                // STS: 4096 steps = 360° (supports negative/multi-turn)
                return (position / 4096 * 360).toFixed(1);
            }
        }
        
        function updateAngleDisplay(cardIdx, position) {
            const angle = calcAngle(cardIdx, position);
            document.getElementById('angle' + cardIdx).textContent = angle + '°';
        }
        
        async function onSlider(cardIdx, value) {
            const pos = parseInt(value);
            document.getElementById('pos' + cardIdx).value = pos;
            updateAngleDisplay(cardIdx, pos);
            if (servos[cardIdx]) {
                await fetch('/api/servo/position', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id: servos[cardIdx].id, position: pos})
                });
            }
        }
        
        async function onPositionInput(cardIdx, value) {
            const pos = parseInt(value);
            if (isNaN(pos)) return;
            
            // Update slider to match
            const slider = document.getElementById('slider' + cardIdx);
            const clampedPos = Math.max(parseInt(slider.min), Math.min(parseInt(slider.max), pos));
            slider.value = clampedPos;
            
            updateAngleDisplay(cardIdx, pos);
            
            if (servos[cardIdx]) {
                await fetch('/api/servo/position', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id: servos[cardIdx].id, position: pos})
                });
            }
        }
        
        async function gotoPos(cardIdx, which) {
            const slider = document.getElementById('slider' + cardIdx);
            let pos;
            if (which === 'min') pos = parseInt(slider.min);
            else if (which === 'max') pos = parseInt(slider.max);
            else pos = Math.floor((parseInt(slider.min) + parseInt(slider.max)) / 2);
            slider.value = pos;
            onSlider(cardIdx, pos);
        }
        
        async function toggleTorque(cardIdx) {
            const servo = servos[cardIdx];
            if (!servo) return;
            
            const btn = document.getElementById('torqueBtn' + cardIdx);
            const isOn = btn.classList.contains('on');
            const newState = !isOn;
            
            btn.textContent = '...';
            btn.disabled = true;
            
            try {
                const resp = await fetch('/api/servo/program', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id: servo.id, action: 'set_torque', value: newState ? 1 : 0})
                });
                const data = await resp.json();
                
                if (data.success) {
                    updateTorqueBtn(cardIdx, newState);
                } else {
                    // Revert to previous state display
                    updateTorqueBtn(cardIdx, isOn);
                    alert('Failed to change torque: ' + (data.error || 'Unknown error'));
                }
            } catch (e) {
                updateTorqueBtn(cardIdx, isOn);
            }
            
            btn.disabled = false;
        }
        
        function updateTorqueBtn(cardIdx, isOn) {
            const btn = document.getElementById('torqueBtn' + cardIdx);
            if (isOn) {
                btn.textContent = '🔒 Torque ON';
                btn.className = 'torque-btn on';
            } else {
                btn.textContent = '🔓 Torque OFF';
                btn.className = 'torque-btn off';
            }
        }
        
        // Step Mode Functions
        let stepModes = {};  // Track step mode state per card
        
        async function toggleStepMode(cardIdx) {
            const servo = servos[cardIdx];
            if (!servo) return;
            
            const toggle = document.getElementById('stepToggle' + cardIdx);
            const controls = document.getElementById('stepControls' + cardIdx);
            const isActive = toggle.classList.contains('active');
            const newState = !isActive;
            
            toggle.textContent = '...';
            toggle.disabled = true;
            
            try {
                const resp = await fetch('/api/servo/step_mode', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        id: servo.id, 
                        enable: newState,
                        speed: 300
                    })
                });
                const data = await resp.json();
                
                if (data.success) {
                    stepModes[cardIdx] = newState;
                    if (newState) {
                        toggle.classList.add('active');
                        toggle.textContent = '✓ Step Mode ON';
                        controls.classList.add('active');
                        // Hide slider in step mode
                        document.querySelector('#card' + cardIdx + ' .slider-container').style.display = 'none';
                        document.getElementById('quickBtns' + cardIdx).style.display = 'none';
                        document.getElementById('regStepControls' + cardIdx).style.display = 'none';
                    } else {
                        toggle.classList.remove('active');
                        toggle.textContent = '🔄 Step Mode';
                        controls.classList.remove('active');
                        // Show slider in normal mode
                        document.querySelector('#card' + cardIdx + ' .slider-container').style.display = 'block';
                        document.getElementById('quickBtns' + cardIdx).style.display = 'flex';
                        document.getElementById('regStepControls' + cardIdx).style.display = 'block';
                    }
                } else {
                    alert('Failed to toggle step mode: ' + (data.error || 'Unknown error'));
                    toggle.textContent = isActive ? '✓ Step Mode ON' : '🔄 Step Mode';
                }
            } catch (e) {
                toggle.textContent = isActive ? '✓ Step Mode ON' : '🔄 Step Mode';
            }
            
            toggle.disabled = false;
        }
        
        async function doStep(cardIdx, direction) {
            const servo = servos[cardIdx];
            if (!servo) return;
            
            const stepSize = parseInt(document.getElementById('stepSize' + cardIdx).value) || 500;
            const steps = stepSize * direction;
            
            try {
                await fetch('/api/servo/step', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id: servo.id, steps: steps})
                });
            } catch (e) {
                console.error('Step error:', e);
            }
        }
        
        async function doRegStep(cardIdx, direction) {
            const servo = servos[cardIdx];
            if (!servo) return;
            
            const stepSize = parseInt(document.getElementById('regStepSize' + cardIdx).value) || 10;
            const posInput = document.getElementById('pos' + cardIdx);
            const slider = document.getElementById('slider' + cardIdx);
            
            let currentPos = parseInt(posInput.value) || 0;
            let newPos = currentPos + (stepSize * direction);
            
            const min = parseInt(slider.min);
            const max = parseInt(slider.max);
            
            newPos = Math.max(min, Math.min(max, newPos));
            
            posInput.value = newPos;
            slider.value = newPos;
            
            try {
                await fetch('/api/servo/position', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({id: servo.id, position: newPos})
                });
            } catch (e) {
                console.error('Position error:', e);
            }
        }
        
        function updateStepModeUI(cardIdx, mode) {
            // Mode 3 = step mode
            const isStepMode = mode === 3;
            const toggle = document.getElementById('stepToggle' + cardIdx);
            const controls = document.getElementById('stepControls' + cardIdx);
            
            stepModes[cardIdx] = isStepMode;
            
                if (isStepMode) {
                toggle.classList.add('active');
                toggle.textContent = '✓ Step Mode ON';
                controls.classList.add('active');
                document.querySelector('#card' + cardIdx + ' .slider-container').style.display = 'none';
                document.getElementById('quickBtns' + cardIdx).style.display = 'none';
                document.getElementById('regStepControls' + cardIdx).style.display = 'none';
            } else {
                toggle.classList.remove('active');
                toggle.textContent = '🔄 Step Mode';
                controls.classList.remove('active');
                document.querySelector('#card' + cardIdx + ' .slider-container').style.display = 'block';
                document.getElementById('quickBtns' + cardIdx).style.display = 'flex';
                document.getElementById('regStepControls' + cardIdx).style.display = 'block';
            }
        }
        
        async function syncMove(position) {
            if (!connected) return;
            for (let i = 0; i < 16; i++) {
                if (servos[i]) {
                    const slider = document.getElementById('slider' + i);
                    const min = parseInt(slider.min);
                    const max = parseInt(slider.max);
                    const pos = Math.max(min, Math.min(max, position));
                    slider.value = pos;
                    onSlider(i, pos);
                }
            }
            setStatus(`Sync move to ${position}`);
        }
        
        async function refreshAll(silent = false) {
            for (let i = 0; i < 16; i++) {
                if (servos[i]) {
                    try {
                        const resp = await fetch(`/api/servo/status?id=${servos[i].id}`);
                        const data = await resp.json();
                        if (data.success) updateCard(i, data);
                    } catch (e) {
                        // Ignore fetch errors during auto-refresh
                    }
                }
            }
            if (!silent) setStatus('Refreshed');
        }
        
        function startAutoRefresh() {
            if (autoRefreshInterval) return;
            autoRefreshInterval = setInterval(() => {
                if (connected && Object.keys(servos).length > 0) {
                    refreshAll(true);  // Silent refresh
                }
            }, 500);  // Refresh every 500ms
        }
        
        function stopAutoRefresh() {
            if (autoRefreshInterval) {
                clearInterval(autoRefreshInterval);
                autoRefreshInterval = null;
            }
        }
        
        async function stopAll() {
            await fetch('/api/stop', {method: 'POST'});
            setStatus('⚠️ STOPPED - Torque disabled');
        }
        
        // Programming Modal
        function openProgram(cardIdx) {
            if (!servos[cardIdx]) {
                alert('Connect servo first');
                return;
            }
            currentProgramServo = servos[cardIdx];  // {id, type}
            const typeLabel = currentProgramServo.type.toUpperCase();
            document.getElementById('modalServoId').textContent = `${typeLabel} ID ${currentProgramServo.id}`;
            document.getElementById('currentId').textContent = currentProgramServo.id;
            document.getElementById('newId').value = '';
            updateModeDropdown(currentProgramServo.type);
            document.getElementById('programModal').classList.add('active');
            readAllSettings();
        }
        
        function closeModal() {
            document.getElementById('programModal').classList.remove('active');
            currentProgramServo = null;
        }
        
        async function readAllSettings() {
            if (!currentProgramServo) return;
            const resp = await fetch(`/api/servo/settings?id=${currentProgramServo.id}`);
            const data = await resp.json();
            if (data.success) {
                document.getElementById('currentId').textContent = currentProgramServo.id;
                const sType = currentProgramServo.type;
                const hasMode = sType === 'sts' || sType === 'hls';
                const isHLS = sType === 'hls';

                // Show/hide STS-only options (STS and HLS both support mode/offset/acc)
                document.querySelectorAll('.sts-only').forEach(el => {
                    el.style.display = hasMode ? 'flex' : 'none';
                });
                document.querySelectorAll('.hls-only').forEach(el => {
                    el.style.display = isHLS ? 'flex' : 'none';
                });

                // Dynamic labels for Overload Protection section (addr 34/35 differ)
                if (isHLS) {
                    document.getElementById('overloadSectionTitle').textContent = 'Current Loop / Protection';
                    document.getElementById('protectionTorqueLabel').textContent = 'Current P Gain:';
                    document.getElementById('protectionTimeLabel').textContent = 'Current I Gain:';
                    document.getElementById('speedLoopTitle').textContent = 'Speed Loop (HLS)';
                } else {
                    document.getElementById('overloadSectionTitle').textContent = 'Overload Protection';
                    document.getElementById('protectionTorqueLabel').textContent = 'Protection Torque:';
                    document.getElementById('protectionTimeLabel').textContent = 'Protection Time (s):';
                    document.getElementById('speedLoopTitle').textContent = 'Speed Loop (STS/SMS)';
                }
                
                // Identity & Mode
                document.getElementById('currentMode').textContent = hasMode ? getModeText(data.mode) : 'N/A (SCS)';
                document.getElementById('currentBaud').textContent = getBaudText(data.baud);
                
                // Angle Limits
                document.getElementById('minLimit').value = data.min_limit || 0;
                document.getElementById('maxLimit').value = data.max_limit || 1023;
                
                // Dead Zone
                document.getElementById('cwDead').value = data.cw_dead || 0;
                document.getElementById('ccwDead').value = data.ccw_dead || 0;
                
                // Offset
                document.getElementById('offset').value = data.offset || 0;
                
                // PID
                document.getElementById('pidP').value = data.pid_p || 0;
                document.getElementById('pidI').value = data.pid_i || 0;
                document.getElementById('pidD').value = data.pid_d || 0;
                
                // Punch & Torque
                document.getElementById('punch').value = data.punch || 0;
                document.getElementById('maxTorque').value = data.max_torque || 1023;
                
                // Protection Limits
                document.getElementById('maxTemp').value = data.max_temp || 85;
                document.getElementById('minVoltage').value = data.min_voltage || 5.0;
                document.getElementById('maxVoltage').value = data.max_voltage || 8.4;
                
                // Overload Protection / Current Loop
                document.getElementById('protectionTorque').value = data.protection_torque || 0;
                document.getElementById('protectionTime').value = data.protection_time || 0;
                document.getElementById('protectionCurrent').value = data.protection_current || 0;
                
                // LED & Alarms
                document.getElementById('ledAlarm').value = data.led_alarm || 0;
                document.getElementById('unloading').value = data.unloading || 0;
                
                // Speed Loop
                document.getElementById('speedP').value = data.speed_p || 0;
                document.getElementById('speedI').value = data.speed_i || 0;
                document.getElementById('acceleration').value = data.acceleration || 0;
                
                // HLS-specific fields
                if (isHLS) {
                    document.getElementById('torqueLimit').value = data.torque_limit || 1000;
                    document.getElementById('sramKp').value = data.sram_kp || 0;
                    document.getElementById('sramKd').value = data.sram_kd || 0;
                    document.getElementById('sramKi').value = data.sram_ki || 0;
                    document.getElementById('secondId').value = data.second_id || 253;
                    document.getElementById('angularRes').value = data.angular_res || 1;
                }
                
                // Update torque status display
                const torqueStatus = document.getElementById('currentTorque');
                const enableBtn = document.getElementById('torqueEnableBtn');
                const disableBtn = document.getElementById('torqueDisableBtn');
                if (data.torque) {
                    torqueStatus.textContent = 'ENABLED';
                    torqueStatus.style.color = '#00dd88';
                    enableBtn.textContent = '✓ Enabled';
                    enableBtn.style.background = 'linear-gradient(135deg, #00dd88 0%, #00aa66 100%)';
                    disableBtn.textContent = 'Disable';
                    disableBtn.style.background = '';
                } else {
                    torqueStatus.textContent = 'DISABLED';
                    torqueStatus.style.color = '#ff4466';
                    disableBtn.textContent = '✓ Disabled';
                    disableBtn.style.background = 'linear-gradient(135deg, #ff4466 0%, #cc3355 100%)';
                    enableBtn.textContent = 'Enable';
                    enableBtn.style.background = '';
                }
            }
        }
        
        function getModeText(mode) {
            const servoType = currentProgramServo ? currentProgramServo.type : 'sts';
            if (servoType === 'hls') {
                const modes = ['Position (Servo)', 'Wheel (Continuous)', 'Electric/Force'];
                return modes[mode] || `Unknown (${mode})`;
            }
            const modes = ['Position (Servo)', 'Wheel (Continuous)', 'PWM', 'Step'];
            return modes[mode] || `Unknown (${mode})`;
        }

        function updateModeDropdown(servoType) {
            const sel = document.getElementById('newMode');
            sel.innerHTML = '';
            const opts = [
                {value: 0, text: 'Position Control (Servo)'},
                {value: 1, text: 'Wheel Mode (Continuous)'},
            ];
            if (servoType === 'hls') {
                opts.push({value: 2, text: 'Electric/Force (Torque)'});
            } else {
                opts.push({value: 2, text: 'PWM Mode'});
                opts.push({value: 3, text: 'Multi-turn Mode'});
            }
            opts.forEach(o => {
                const opt = document.createElement('option');
                opt.value = o.value;
                opt.textContent = o.text;
                sel.appendChild(opt);
            });
        }
        
        function getBaudText(baud) {
            const bauds = ['1M', '500K', '250K', '128K', '115200', '76800', '57600', '38400'];
            return bauds[baud] || `Unknown (${baud})`;
        }
        
        async function readMode() {
            const resp = await fetch(`/api/servo/settings?id=${currentProgramServo.id}`);
            const data = await resp.json();
            if (data.success) {
                document.getElementById('currentMode').textContent = getModeText(data.mode);
            }
        }
        
        async function readBaud() {
            const resp = await fetch(`/api/servo/settings?id=${currentProgramServo.id}`);
            const data = await resp.json();
            if (data.success) {
                document.getElementById('currentBaud').textContent = getBaudText(data.baud);
            }
        }
        
        async function changeId() {
            const newId = parseInt(document.getElementById('newId').value);
            if (!newId || newId < 1 || newId > 253) {
                alert('Enter valid ID (1-253)');
                return;
            }
            if (!confirm(`Change servo ID from ${currentProgramServo.id} to ${newId}?\\n\\nYou will need to reconnect after this.`)) return;
            
            const resp = await fetch('/api/servo/program', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id: currentProgramServo.id, action: 'change_id', value: newId})
            });
            const data = await resp.json();
            if (data.success) {
                alert(`ID changed to ${newId}. Please reconnect.`);
                closeModal();
                scanAll();
            } else {
                alert('Failed: ' + data.error);
            }
        }
        
        async function changeMode() {
            const mode = parseInt(document.getElementById('newMode').value);
            const resp = await fetch('/api/servo/program', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id: currentProgramServo.id, action: 'change_mode', value: mode})
            });
            const data = await resp.json();
            if (data.success) {
                setStatus(`Mode changed to ${getModeText(mode)}`);
                readMode();
            } else {
                alert('Failed: ' + data.error);
            }
        }
        
        async function setMinLimit() {
            const val = parseInt(document.getElementById('minLimit').value);
            const resp = await fetch('/api/servo/program', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id: currentProgramServo.id, action: 'set_min_limit', value: val})
            });
            const data = await resp.json();
            if (data.success) setStatus('Min limit set to ' + val);
            else alert('Failed: ' + data.error);
        }
        
        async function setMaxLimit() {
            const val = parseInt(document.getElementById('maxLimit').value);
            const resp = await fetch('/api/servo/program', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id: currentProgramServo.id, action: 'set_max_limit', value: val})
            });
            const data = await resp.json();
            if (data.success) setStatus('Max limit set to ' + val);
            else alert('Failed: ' + data.error);
        }
        
        async function changeBaud() {
            const baud = parseInt(document.getElementById('newBaud').value);
            if (!confirm('Changing baud rate requires power cycle. Continue?')) return;
            const resp = await fetch('/api/servo/program', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id: currentProgramServo.id, action: 'change_baud', value: baud})
            });
            const data = await resp.json();
            if (data.success) {
                alert('Baud rate changed. Power cycle servo and reconnect.');
            } else {
                alert('Failed: ' + data.error);
            }
        }
        
        async function setCwDead() {
            const val = parseInt(document.getElementById('cwDead').value);
            const resp = await fetch('/api/servo/program', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id: currentProgramServo.id, action: 'set_cw_dead', value: val})
            });
            const data = await resp.json();
            if (data.success) setStatus('CW dead zone set to ' + val);
            else alert('Failed: ' + data.error);
        }
        
        async function setCcwDead() {
            const val = parseInt(document.getElementById('ccwDead').value);
            const resp = await fetch('/api/servo/program', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id: currentProgramServo.id, action: 'set_ccw_dead', value: val})
            });
            const data = await resp.json();
            if (data.success) setStatus('CCW dead zone set to ' + val);
            else alert('Failed: ' + data.error);
        }
        
        async function setOffset() {
            const val = parseInt(document.getElementById('offset').value);
            const resp = await fetch('/api/servo/program', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id: currentProgramServo.id, action: 'set_offset', value: val})
            });
            const data = await resp.json();
            if (data.success) setStatus('Offset set to ' + val);
            else alert('Failed: ' + data.error);
        }
        
        // PID Settings
        async function setPidP() {
            await programValue('pid_p', 'pidP', 'P coefficient');
        }
        async function setPidI() {
            await programValue('pid_i', 'pidI', 'I coefficient');
        }
        async function setPidD() {
            await programValue('pid_d', 'pidD', 'D coefficient');
        }
        
        // Punch & Torque Limit
        async function setPunch() {
            await programValue('punch', 'punch', 'Punch');
        }
        async function setMaxTorque() {
            await programValue('max_torque', 'maxTorque', 'Max torque');
        }
        
        // Protection Limits
        async function setMaxTemp() {
            await programValue('max_temp', 'maxTemp', 'Max temperature');
        }
        async function setMinVoltage() {
            const val = parseFloat(document.getElementById('minVoltage').value);
            const raw = Math.round(val * 10);  // Convert to 0.1V units
            await programRaw('min_voltage', raw, 'Min voltage');
        }
        async function setMaxVoltage() {
            const val = parseFloat(document.getElementById('maxVoltage').value);
            const raw = Math.round(val * 10);  // Convert to 0.1V units
            await programRaw('max_voltage', raw, 'Max voltage');
        }
        
        // Overload Protection
        async function setProtectionTorque() {
            await programValue('protection_torque', 'protectionTorque', 'Protection torque');
        }
        async function setProtectionTime() {
            await programValue('protection_time', 'protectionTime', 'Protection time');
        }
        async function setProtectionCurrent() {
            await programValue('protection_current', 'protectionCurrent', 'Protection current');
        }
        
        // LED & Alarms
        async function setLedAlarm() {
            await programValue('led_alarm', 'ledAlarm', 'LED alarm');
        }
        async function setUnloading() {
            await programValue('unloading', 'unloading', 'Unloading condition');
        }
        
        // Speed Loop
        async function setSpeedP() {
            await programValue('speed_p', 'speedP', 'Speed P');
        }
        async function setSpeedI() {
            await programValue('speed_i', 'speedI', 'Speed I');
        }
        async function setAcceleration() {
            await programValue('acceleration', 'acceleration', 'Acceleration');
        }

        // HLS-specific setters
        async function setTorqueLimit() {
            await programValue('torque_limit', 'torqueLimit', 'Torque Limit');
        }
        async function setSramKp() {
            await programValue('sram_kp', 'sramKp', 'SRAM Kp');
        }
        async function setSramKd() {
            await programValue('sram_kd', 'sramKd', 'SRAM Kd');
        }
        async function setSramKi() {
            await programValue('sram_ki', 'sramKi', 'SRAM Ki');
        }
        async function setSecondId() {
            await programValue('second_id', 'secondId', 'Second ID');
        }
        async function setAngularRes() {
            await programValue('angular_res', 'angularRes', 'Angular Resolution');
        }

        // Generic helper to program a value
        async function programValue(action, inputId, label) {
            const val = parseInt(document.getElementById(inputId).value);
            await programRaw(action, val, label);
        }
        
        async function programRaw(action, value, label) {
            const resp = await fetch('/api/servo/program', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id: currentProgramServo.id, action: action, value: value})
            });
            const data = await resp.json();
            if (data.success) setStatus(label + ' set successfully');
            else alert('Failed: ' + data.error);
        }
        
        async function setTorque(enable) {
            const enableBtn = document.getElementById('torqueEnableBtn');
            const disableBtn = document.getElementById('torqueDisableBtn');
            const statusEl = document.getElementById('currentTorque');
            
            // Show loading
            if (enable) {
                enableBtn.textContent = '...';
            } else {
                disableBtn.textContent = '...';
            }
            
            const resp = await fetch('/api/servo/program', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id: currentProgramServo.id, action: 'set_torque', value: enable ? 1 : 0})
            });
            const data = await resp.json();
            
            if (data.success) {
                if (enable) {
                    enableBtn.textContent = '✓ Enabled';
                    enableBtn.style.background = 'linear-gradient(135deg, #00dd88 0%, #00aa66 100%)';
                    disableBtn.textContent = 'Disable';
                    disableBtn.style.background = '';
                    statusEl.textContent = 'ENABLED';
                    statusEl.style.color = '#00dd88';
                } else {
                    disableBtn.textContent = '✓ Disabled';
                    disableBtn.style.background = 'linear-gradient(135deg, #ff4466 0%, #cc3355 100%)';
                    enableBtn.textContent = 'Enable';
                    enableBtn.style.background = '';
                    statusEl.textContent = 'DISABLED';
                    statusEl.style.color = '#ff4466';
                }
                setStatus('Torque ' + (enable ? 'enabled' : 'disabled'));
            } else {
                enableBtn.textContent = 'Enable';
                disableBtn.textContent = 'Disable';
                alert('Failed: ' + data.error);
            }
        }
        
        async function lockEprom() {
            const resp = await fetch('/api/servo/program', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id: currentProgramServo.id, action: 'lock_eprom'})
            });
            const data = await resp.json();
            if (data.success) setStatus('EPROM locked');
            else alert('Failed: ' + data.error);
        }
        
        async function unlockEprom() {
            const resp = await fetch('/api/servo/program', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({id: currentProgramServo.id, action: 'unlock_eprom'})
            });
            const data = await resp.json();
            if (data.success) setStatus('EPROM unlocked - ready to write');
            else alert('Failed: ' + data.error);
        }
        
        // Close modal on escape
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeModal();
        });
        
        // Initialize
        createCards();
        loadPorts();
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/ports')
def get_ports():
    """Get available serial ports for servo adapters
    
    Supports:
      - Feetech URT-1 (CH340/CH343 USB)
      - Waveshare Bus Servo Adapter v1.1 (CH340/CP210x USB)
      - Raspberry Pi 4 Hardware UARTs (connected to URT-1 via GPIO: /dev/serial0, /dev/ttyAMA0..4)
      - Other USB-TTL and SBC hardware UART adapters
    """
    all_ports = []
    seen_devices = set()
    
    # 1. Check for Linux / Raspberry Pi hardware UARTs
    # On Raspberry Pi OS, /dev/serial0 is the primary UART alias (usually ttyAMA0 or ttyS0).
    # Pi 4 also provides 4 additional PL011 UARTs (ttyAMA1 to ttyAMA4).
    if sys.platform.startswith('linux'):
        pi_uart_candidates = [
            ('/dev/serial0', 'Raspberry Pi Primary UART (URT-1)'),
            ('/dev/serial1', 'Raspberry Pi Secondary UART (URT-1)'),
            ('/dev/ttyAMA0', 'Raspberry Pi Hardware UART0 (PL011 / URT-1)'),
            ('/dev/ttyAMA1', 'Raspberry Pi 4 Hardware UART2 (PL011 / URT-1)'),
            ('/dev/ttyAMA2', 'Raspberry Pi 4 Hardware UART3 (PL011 / URT-1)'),
            ('/dev/ttyAMA3', 'Raspberry Pi 4 Hardware UART4 (PL011 / URT-1)'),
            ('/dev/ttyAMA4', 'Raspberry Pi 4 Hardware UART5 (PL011 / URT-1)'),
            ('/dev/ttyS0', 'Raspberry Pi Mini UART (URT-1)'),
        ]
        for dev_path, desc in pi_uart_candidates:
            if os.path.exists(dev_path) and dev_path not in seen_devices:
                real_target = os.path.realpath(dev_path)
                detail_desc = desc
                if real_target != dev_path:
                    detail_desc += f" -> {os.path.basename(real_target)}"
                
                seen_devices.add(dev_path)
                all_ports.append({
                    'device': dev_path,
                    'description': detail_desc,
                    'type': 'Pi UART (URT-1)',
                    'interface': 'uart'
                })

        # Also check NVIDIA Jetson / other SBC hardware UARTs
        for dev_path in glob.glob('/dev/ttyTHS*'):
            if dev_path not in seen_devices and os.path.exists(dev_path):
                seen_devices.add(dev_path)
                all_ports.append({
                    'device': dev_path,
                    'description': f'NVIDIA Jetson UART ({os.path.basename(dev_path)})',
                    'type': 'Jetson UART (URT-1)',
                    'interface': 'uart'
                })

    # 2. Check standard USB-serial adapters and COM ports via pyserial
    KNOWN_VIDS = [
        0x1A86,  # CH340/CH341/CH343 (URT-1, Waveshare)
        0x10C4,  # Silicon Labs CP210x
        0x0403,  # FTDI
        0x067B,  # Prolific PL2303
        0x2341,  # Arduino
    ]
    
    for p in serial.tools.list_ports.comports():
        if p.device in seen_devices:
            continue

        desc = (p.description or '').upper()
        hwid = (p.hwid or '').upper()
        device_upper = p.device.upper()
        
        # Skip Bluetooth and debug ports first
        if 'BLUETOOTH' in desc or 'BLUETOOTH' in hwid or 'BTHENUM' in hwid:
            continue
        if 'DEBUG' in device_upper:
            continue
        
        # Check for Raspberry Pi / hardware UART entries returned by comports()
        if any(u in device_upper for u in ['TTYAMA', 'SERIAL0', 'SERIAL1']):
            seen_devices.add(p.device)
            all_ports.append({
                'device': p.device,
                'description': p.description or 'Raspberry Pi UART (URT-1)',
                'type': 'Pi UART (URT-1)',
                'interface': 'uart'
            })
            continue
        elif 'TTYTHS' in device_upper:
            seen_devices.add(p.device)
            all_ports.append({
                'device': p.device,
                'description': p.description or 'Jetson UART (URT-1)',
                'type': 'Jetson UART (URT-1)',
                'interface': 'uart'
            })
            continue

        # Check by VID first (most reliable)
        is_adapter = p.vid in KNOWN_VIDS if p.vid else False
        
        # Also check by name patterns
        if not is_adapter:
            patterns = ['USBSERIAL', 'USBMODEM', 'TTYUSB', 'TTYACM',
                        'USB SERIAL', 'USB SINGLE SERIAL', 'USB-ENHANCED-SERIAL',
                        'CH340', 'CH341', 'CH343', 'CP210', 'FTDI', 'FT232', 'PROLIFIC']
            is_adapter = any(pat in desc or pat in device_upper for pat in patterns)
        
        if is_adapter:
            seen_devices.add(p.device)
            # Identify adapter type
            if p.vid == 0x1A86:
                # WCH chips: CH340, CH341, CH343
                if 'CH343' in desc:
                    adapter_type = 'CH343 (URT-1)'
                elif 'SINGLE' in desc:
                    adapter_type = 'Waveshare (CH340)'
                else:
                    adapter_type = 'CH340 (URT-1)'
            elif p.vid == 0x10C4:
                adapter_type = 'CP210x'
            elif p.vid == 0x0403:
                adapter_type = 'FTDI'
            elif 'CH343' in desc:
                adapter_type = 'CH343 (URT-1)'
            elif 'CH340' in desc or 'CH341' in desc:
                adapter_type = 'CH340 (URT-1)'
            else:
                adapter_type = 'USB-Serial'
            
            all_ports.append({
                'device': p.device,
                'description': p.description,
                'type': adapter_type,
                'interface': 'usb'
            })
    
    return jsonify({
        'ports': [p['device'] for p in all_ports],
        'details': all_ports,
        'connected_port': controller['port'],
        'connected_baud': controller.get('baudrate', 1000000),
        'connected': bool(controller['servo'] and controller['servo'].is_open())
    })

@app.route('/api/connect', methods=['POST'])
def connect():
    data = request.json or {}
    port = data.get('port')
    baudrate = int(data.get('baudrate', 1000000))
    
    if not port:
        return jsonify({'success': False, 'error': 'No port specified'})
    
    with lock:
        if controller['servo']:
            controller['servo'].close()
        
        controller['servo'] = FeetechServo()
        if controller['servo'].open(port, baudrate=baudrate):
            controller['port'] = port
            controller['baudrate'] = baudrate
            return jsonify({'success': True, 'port': port, 'baudrate': baudrate})
        else:
            controller['servo'] = None
            controller['port'] = None
            return jsonify({'success': False, 'error': f'Could not open {port} at {baudrate:,} baud'})

@app.route('/api/disconnect', methods=['POST'])
def disconnect():
    with lock:
        if controller['servo']:
            controller['servo'].close()
            controller['servo'] = None
            controller['port'] = None
            controller['connected_servos'] = {}
    return jsonify({'success': True})

@app.route('/api/servo/type', methods=['POST'])
def servo_set_type():
    """Override auto-detected servo type (SCS, STS, or HLS)"""
    data = request.json
    servo_id = data.get('id')
    servo_type = data.get('type', '').lower()

    if servo_type not in ('scs', 'sts', 'hls'):
        return jsonify({'success': False, 'error': 'Type must be scs, sts, or hls'})

    with lock:
        controller['servo_types'][servo_id] = servo_type
        if controller['servo']:
            controller['servo'].configure_for_type(servo_type)
    return jsonify({'success': True, 'type': servo_type})

@app.route('/api/scan')
def scan():
    found = []
    with lock:
        if controller['servo']:
            for sid in range(1, 31):  # Scan IDs 1-30
                try:
                    if controller['servo'].ping(sid) >= 0:
                        found.append(sid)
                except:
                    pass
    return jsonify({'found': found})

@app.route('/api/servo/connect', methods=['POST'])
def servo_connect():
    data = request.json
    card_idx = data.get('card')
    servo_id = data.get('id')
    
    with lock:
        if not controller['servo']:
            return jsonify({'success': False, 'error': 'Not connected'})
        
        result = controller['servo'].ping(servo_id)
        if result < 0:
            return jsonify({'success': False, 'error': 'No response'})
        
        try:
            servo = controller['servo']
            
            # Detect servo type
            servo_type = detect_servo_type(servo, servo_id)
            controller['servo_types'][servo_id] = servo_type
            
            # Configure for detected servo type
            servo.configure_for_type(servo_type)
            type_class = get_servo_type(servo_type)
            
            # Read position based on type capabilities
            if type_class.supports_multi_turn:
                pos = servo.read_position_signed(servo_id)
                min_pos = servo.read_register(servo_id, 9)
                max_pos = servo.read_register(servo_id, 11)
            else:
                pos = servo.read_position(servo_id)
                min_pos = servo.read_register(servo_id, 9)
                max_pos = servo.read_register(servo_id, 11)
                if max_pos <= 0:
                    max_pos = type_class.max_position
            
            voltage = servo.read_voltage(servo_id)
            temp = servo.read_temperature(servo_id)
            load = servo.read_load(servo_id)
            torque = servo.read_register(servo_id, 40)
            
            current_ma = None
            if servo_type == 'hls':
                raw_current = servo.read_register(servo_id, 69)
                if raw_current is not None and raw_current >= 0:
                    current_ma = raw_current * 6.5
            
            controller['connected_servos'][card_idx] = servo_id
            
            return jsonify({
                'success': True,
                'position': pos,
                'min': min_pos,
                'max': max_pos,
                'voltage': voltage if voltage >= 0 else None,
                'temp': temp if temp >= 0 else None,
                'load': load if load >= 0 else None,
                'current': current_ma,
                'type': servo_type,
                'torque': torque == 1
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

@app.route('/api/servo/position', methods=['POST'])
def servo_position():
    data = request.json
    servo_id = data.get('id')
    position = data.get('position')
    
    with lock:
        if controller['servo']:
            try:
                servo = controller['servo']
                servo_type = controller['servo_types'].get(servo_id, 'sts')
                servo.configure_for_type(servo_type)
                
                if servo_type == 'hls':
                    # Read the current SRAM Torque Limit so moves respect it
                    torque_lim = servo.read_register(servo_id, 48)
                    if torque_lim < 0:
                        torque_lim = 1000
                    servo.write_position(servo_id, position, speed=1000, torque=torque_lim)
                else:
                    servo.write_position(servo_id, position, speed=1000)
                return jsonify({'success': True})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
    return jsonify({'success': False, 'error': 'Not connected'})

@app.route('/api/servo/status')
def servo_status():
    servo_id = request.args.get('id', type=int)
    
    with lock:
        if not controller['servo']:
            return jsonify({'success': False})
        
        try:
            servo = controller['servo']
            servo_type = controller['servo_types'].get(servo_id, 'sts')
            
            # Configure for detected servo type
            servo.configure_for_type(servo_type)
            type_class = get_servo_type(servo_type)
            
            # Read position based on type capabilities
            if type_class.supports_multi_turn:
                pos = servo.read_position_signed(servo_id)
                min_pos = servo.read_register(servo_id, 9)
                max_pos = servo.read_register(servo_id, 11)
            else:
                pos = servo.read_position(servo_id)
                min_pos = servo.read_register(servo_id, 9)
                max_pos = servo.read_register(servo_id, 11)
                if max_pos <= 0:
                    max_pos = type_class.max_position
            
            voltage = servo.read_voltage(servo_id)
            temp = servo.read_temperature(servo_id)
            load = servo.read_load(servo_id)
            torque = servo.read_register(servo_id, 40)
            
            # Read mode for step mode detection
            if type_class.supports_mode:
                mode = servo.read_register(servo_id, type_class.mode_register)
            else:
                mode = 0
            
            # Present current (HLS has sign-magnitude at addr 69)
            current_ma = None
            if servo_type == 'hls':
                raw_current = servo.read_register(servo_id, 69)
                if raw_current is not None and raw_current >= 0:
                    current_ma = raw_current * 6.5
            
            return jsonify({
                'success': True,
                'position': pos,
                'min': min_pos,
                'max': max_pos,
                'voltage': voltage if voltage >= 0 else None,
                'temp': temp if temp >= 0 else None,
                'load': load if load >= 0 else None,
                'current': current_ma,
                'torque': torque == 1,
                'mode': mode if mode >= 0 else 0
            })
        except:
            return jsonify({'success': False})

@app.route('/api/servo/settings')
def servo_settings():
    servo_id = request.args.get('id', type=int)
    
    with lock:
        if not controller['servo']:
            return jsonify({'success': False})
        
        try:
            servo = controller['servo']
            servo_type = controller['servo_types'].get(servo_id, 'sts')
            
            # Configure for detected servo type
            servo.configure_for_type(servo_type)
            type_class = get_servo_type(servo_type)
            
            # Common registers
            baud = servo.read_register(servo_id, 6)
            cw_dead = servo.read_register(servo_id, 26)
            ccw_dead = servo.read_register(servo_id, 27)
            
            # Read limits based on type capabilities
            if type_class.supports_multi_turn:
                min_limit = servo.read_register(servo_id, 9)
                max_limit = servo.read_register(servo_id, 11)
            else:
                min_limit = servo.read_register(servo_id, 9)
                max_limit = servo.read_register(servo_id, 11)
                if max_limit <= 0:
                    max_limit = type_class.max_position
            
            # Read mode if supported
            if type_class.supports_mode:
                mode = servo.read_register(servo_id, type_class.mode_register)
            else:
                mode = 0  # Default to position mode
            
            # Read offset if supported (uses sign-magnitude encoding)
            if type_class.supports_offset:
                try:
                    offset = servo.read_register(servo_id, type_class.offset_register)
                except:
                    offset = 0
            else:
                offset = 0
            
            # Read torque status
            torque = servo.read_register(servo_id, 40)
            
            # Read all EPROM settings
            pid_p = servo.read_register(servo_id, 21)
            pid_i = servo.read_register(servo_id, 22)
            pid_d = servo.read_register(servo_id, 23)
            punch = servo.read_register(servo_id, 24)
            max_torque = servo.read_register(servo_id, 16)
            max_temp = servo.read_register(servo_id, 13)
            min_voltage = servo.read_register(servo_id, 15)
            max_voltage = servo.read_register(servo_id, 14)
            protection_torque = servo.read_register(servo_id, 34)
            protection_time = servo.read_register(servo_id, 35)
            protection_current = servo.read_register(servo_id, 28)
            led_alarm = servo.read_register(servo_id, 20)
            unloading = servo.read_register(servo_id, 19)
            
            # Speed loop (STS and HLS)
            if type_class.supports_acceleration:
                speed_p = servo.read_register(servo_id, 37)
                speed_i = servo.read_register(servo_id, 39)
                acceleration = servo.read_register(servo_id, 41)
            else:
                speed_p = 0
                speed_i = 0
                acceleration = 0
            
            # HLS-specific registers
            hls_data = {}
            if servo_type == 'hls':
                torque_limit = servo.read_register(servo_id, 48)
                sram_kp = servo.read_byte(servo_id, 50)
                sram_kd = servo.read_byte(servo_id, 51)
                sram_ki = servo.read_byte(servo_id, 52)
                second_id = servo.read_byte(servo_id, 7)
                angular_res = servo.read_byte(servo_id, 30)
                hls_data = {
                    'torque_limit': torque_limit if torque_limit >= 0 else 1000,
                    'sram_kp': sram_kp if sram_kp >= 0 else 0,
                    'sram_kd': sram_kd if sram_kd >= 0 else 0,
                    'sram_ki': sram_ki if sram_ki >= 0 else 0,
                    'second_id': second_id if second_id >= 0 else 253,
                    'angular_res': angular_res if angular_res >= 0 else 1,
                }
            
            result = {
                'success': True,
                'type': servo_type,
                'mode': mode if mode >= 0 else 0,
                'baud': baud if baud >= 0 else 0,
                'min_limit': min_limit,
                'max_limit': max_limit,
                'cw_dead': cw_dead if cw_dead >= 0 else 0,
                'ccw_dead': ccw_dead if ccw_dead >= 0 else 0,
                'offset': offset,
                'torque': torque == 1,
                # PID
                'pid_p': pid_p if pid_p >= 0 else 0,
                'pid_i': pid_i if pid_i >= 0 else 0,
                'pid_d': pid_d if pid_d >= 0 else 0,
                # Punch & Torque
                'punch': punch if punch >= 0 else 0,
                'max_torque': max_torque if max_torque >= 0 else 1023,
                # Protection
                'max_temp': max_temp if max_temp >= 0 else 85,
                'min_voltage': (min_voltage / 10.0) if min_voltage >= 0 else 5.0,
                'max_voltage': (max_voltage / 10.0) if max_voltage >= 0 else 8.4,
                'protection_torque': protection_torque if protection_torque >= 0 else 0,
                'protection_time': protection_time if protection_time >= 0 else 0,
                'protection_current': protection_current if protection_current >= 0 else 0,
                # LED & Alarms
                'led_alarm': led_alarm if led_alarm >= 0 else 0,
                'unloading': unloading if unloading >= 0 else 0,
                # Speed loop
                'speed_p': speed_p if speed_p >= 0 else 0,
                'speed_i': speed_i if speed_i >= 0 else 0,
                'acceleration': acceleration if acceleration >= 0 else 0,
            }
            result.update(hls_data)
            return jsonify(result)
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

@app.route('/api/servo/program', methods=['POST'])
def servo_program():
    data = request.json
    servo_id = data.get('id')
    action = data.get('action')
    value = data.get('value', 0)
    
    with lock:
        if not controller['servo']:
            return jsonify({'success': False, 'error': 'Not connected'})
        
        try:
            servo = controller['servo']
            servo_type = controller['servo_types'].get(servo_id, 'sts')
            
            # Configure for detected servo type
            servo.configure_for_type(servo_type)
            type_class = get_servo_type(servo_type)
            
            if action == 'unlock_eprom':
                servo.unlock_eprom(servo_id, servo_type)
                return jsonify({'success': True})
            
            elif action == 'lock_eprom':
                servo.lock_eprom(servo_id, servo_type)
                return jsonify({'success': True})
            
            elif action == 'change_id':
                servo.set_id(servo_id, value, servo_type)
                # Update servo type mapping
                controller['servo_types'][value] = controller['servo_types'].pop(servo_id, 'sts')
                return jsonify({'success': True})
            
            elif action == 'change_mode':
                if not type_class.supports_mode:
                    return jsonify({'success': False, 'error': f'{type_class.name.upper()} servos do not support mode change'})
                servo.unlock_eprom(servo_id, servo_type)
                servo.write_register(servo_id, type_class.mode_register, value)
                servo.lock_eprom(servo_id, servo_type)
                return jsonify({'success': True})
            
            elif action == 'set_min_limit':
                servo.unlock_eprom(servo_id, servo_type)
                # STS/SMS uses sign-magnitude for signed limits, SCS is unsigned
                if type_class.supports_multi_turn:
                    servo.write_register(servo_id, 9, value)
                else:
                    servo.write_register(servo_id, 9, max(0, value))
                servo.lock_eprom(servo_id, servo_type)
                return jsonify({'success': True})
            
            elif action == 'set_max_limit':
                servo.unlock_eprom(servo_id, servo_type)
                # STS/SMS uses sign-magnitude for signed limits, SCS is unsigned
                if type_class.supports_multi_turn:
                    servo.write_register(servo_id, 11, value)
                else:
                    servo.write_register(servo_id, 11, max(0, value))
                servo.lock_eprom(servo_id, servo_type)
                return jsonify({'success': True})
            
            elif action == 'change_baud':
                servo.set_baud_rate(servo_id, value, servo_type)
                return jsonify({'success': True})
            
            elif action == 'set_cw_dead':
                servo.unlock_eprom(servo_id, servo_type)
                servo.write_register(servo_id, 26, value)
                servo.lock_eprom(servo_id, servo_type)
                return jsonify({'success': True})
            
            elif action == 'set_ccw_dead':
                servo.unlock_eprom(servo_id, servo_type)
                servo.write_register(servo_id, 27, value)
                servo.lock_eprom(servo_id, servo_type)
                return jsonify({'success': True})
            
            elif action == 'set_offset':
                if not type_class.supports_offset:
                    return jsonify({'success': False, 'error': f'{type_class.name.upper()} servos do not support offset'})
                servo.set_offset(servo_id, value)
                return jsonify({'success': True})
            
            elif action == 'set_torque':
                servo.enable_torque(servo_id, value == 1)
                return jsonify({'success': True})
            
            # PID Settings
            elif action == 'pid_p':
                servo.unlock_eprom(servo_id, servo_type)
                servo.write_register(servo_id, 21, value)
                servo.lock_eprom(servo_id, servo_type)
                return jsonify({'success': True})
            
            elif action == 'pid_i':
                servo.unlock_eprom(servo_id, servo_type)
                servo.write_register(servo_id, 22, value)
                servo.lock_eprom(servo_id, servo_type)
                return jsonify({'success': True})
            
            elif action == 'pid_d':
                servo.unlock_eprom(servo_id, servo_type)
                servo.write_register(servo_id, 23, value)
                servo.lock_eprom(servo_id, servo_type)
                return jsonify({'success': True})
            
            # Punch & Torque
            elif action == 'punch':
                servo.unlock_eprom(servo_id, servo_type)
                servo.write_register(servo_id, 24, value)
                servo.lock_eprom(servo_id, servo_type)
                return jsonify({'success': True})
            
            elif action == 'max_torque':
                servo.unlock_eprom(servo_id, servo_type)
                servo.write_register(servo_id, 16, value)
                servo.lock_eprom(servo_id, servo_type)
                return jsonify({'success': True})
            
            # Protection Limits
            elif action == 'max_temp':
                servo.unlock_eprom(servo_id, servo_type)
                servo.write_register(servo_id, 13, value)
                servo.lock_eprom(servo_id, servo_type)
                return jsonify({'success': True})
            
            elif action == 'min_voltage':
                servo.unlock_eprom(servo_id, servo_type)
                servo.write_register(servo_id, 15, value)
                servo.lock_eprom(servo_id, servo_type)
                return jsonify({'success': True})
            
            elif action == 'max_voltage':
                servo.unlock_eprom(servo_id, servo_type)
                servo.write_register(servo_id, 14, value)
                servo.lock_eprom(servo_id, servo_type)
                return jsonify({'success': True})
            
            # Overload Protection
            elif action == 'protection_torque':
                servo.unlock_eprom(servo_id, servo_type)
                servo.write_register(servo_id, 34, value)
                servo.lock_eprom(servo_id, servo_type)
                return jsonify({'success': True})
            
            elif action == 'protection_time':
                servo.unlock_eprom(servo_id, servo_type)
                servo.write_register(servo_id, 35, value)
                servo.lock_eprom(servo_id, servo_type)
                return jsonify({'success': True})
            
            elif action == 'protection_current':
                servo.unlock_eprom(servo_id, servo_type)
                servo.write_register(servo_id, 28, value)
                servo.lock_eprom(servo_id, servo_type)
                return jsonify({'success': True})
            
            # LED & Alarms
            elif action == 'led_alarm':
                servo.unlock_eprom(servo_id, servo_type)
                servo.write_register(servo_id, 20, value)
                servo.lock_eprom(servo_id, servo_type)
                return jsonify({'success': True})
            
            elif action == 'unloading':
                servo.unlock_eprom(servo_id, servo_type)
                servo.write_register(servo_id, 19, value)
                servo.lock_eprom(servo_id, servo_type)
                return jsonify({'success': True})
            
            # Speed Loop (STS only)
            elif action == 'speed_p':
                servo.unlock_eprom(servo_id, servo_type)
                servo.write_register(servo_id, 37, value)
                servo.lock_eprom(servo_id, servo_type)
                return jsonify({'success': True})
            
            elif action == 'speed_i':
                servo.unlock_eprom(servo_id, servo_type)
                servo.write_register(servo_id, 39, value)
                servo.lock_eprom(servo_id, servo_type)
                return jsonify({'success': True})
            
            elif action == 'acceleration':
                # Acceleration is in SRAM, no EPROM unlock needed
                servo.write_register(servo_id, 41, value)
                return jsonify({'success': True})
            
            # HLS SRAM registers (no EPROM unlock needed)
            elif action == 'torque_limit':
                servo.write_word(servo_id, 48, value)
                return jsonify({'success': True})
            
            elif action == 'sram_kp':
                servo.write_byte(servo_id, 50, value)
                return jsonify({'success': True})
            
            elif action == 'sram_kd':
                servo.write_byte(servo_id, 51, value)
                return jsonify({'success': True})
            
            elif action == 'sram_ki':
                servo.write_byte(servo_id, 52, value)
                return jsonify({'success': True})
            
            # HLS EPROM registers
            elif action == 'second_id':
                servo.unlock_eprom(servo_id, servo_type)
                servo.write_byte(servo_id, 7, value)
                servo.lock_eprom(servo_id, servo_type)
                return jsonify({'success': True})
            
            elif action == 'angular_res':
                servo.unlock_eprom(servo_id, servo_type)
                servo.write_byte(servo_id, 30, value)
                servo.lock_eprom(servo_id, servo_type)
                return jsonify({'success': True})
            
            else:
                return jsonify({'success': False, 'error': f'Unknown action: {action}'})
                
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)})

@app.route('/api/servo/step', methods=['POST'])
def servo_step():
    """Queue servo step commands to prevent drift"""
    data = request.json
    servo_id = data.get('id')
    steps = data.get('steps', 0)
    
    with lock:
        if controller['servo']:
            step_queues[servo_id].append(steps)
            return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Not connected'})

@app.route('/api/servo/step_mode', methods=['POST'])
def servo_step_mode():
    """Enable or disable step mode"""
    data = request.json
    servo_id = data.get('id')
    enable = data.get('enable', True)
    speed = data.get('speed', 300)
    
    with lock:
        if controller['servo']:
            try:
                servo = controller['servo']
                servo_type = controller['servo_types'].get(servo_id, 'sts')
                servo.configure_for_type(servo_type)
                
                if enable:
                    servo.enable_step_mode(servo_id, speed=speed, acc=50)
                else:
                    servo.disable_step_mode(servo_id)
                
                return jsonify({'success': True})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
    return jsonify({'success': False, 'error': 'Not connected'})

@app.route('/api/servo/step_speed', methods=['POST'])
def servo_step_speed():
    """Set step mode speed"""
    data = request.json
    servo_id = data.get('id')
    speed = data.get('speed', 300)
    
    with lock:
        if controller['servo']:
            try:
                servo = controller['servo']
                servo_type = controller['servo_types'].get(servo_id, 'sts')
                servo.configure_for_type(servo_type)
                
                servo.set_step_speed(servo_id, speed)
                return jsonify({'success': True})
            except Exception as e:
                return jsonify({'success': False, 'error': str(e)})
    return jsonify({'success': False, 'error': 'Not connected'})

@app.route('/api/stop', methods=['POST'])
def stop_all():
    with lock:
        if controller['servo']:
            for servo_id in controller['connected_servos'].values():
                try:
                    controller['servo'].enable_torque(servo_id, False)
                except:
                    pass
    return jsonify({'success': True})


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Feetech Servo Control - Web Interface")
    parser.add_argument("--port", "-p", type=int, default=8080, help="Web server port to listen on (default: 8080)")
    parser.add_argument("--host", default="0.0.0.0", help="Host interface to bind to (default: 0.0.0.0)")
    parser.add_argument("--serial-port", "--device", "-s", default=None,
                        help="Serial port to auto-connect to (e.g. /dev/serial0, /dev/ttyAMA0, /dev/ttyUSB0)")
    parser.add_argument("--baudrate", "-b", type=int, default=1000000,
                        help="Serial communication baud rate (default: 1000000)")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    args = parser.parse_args()

    # Auto-connect if serial port specified via CLI
    if args.serial_port:
        with lock:
            controller['servo'] = FeetechServo()
            if controller['servo'].open(args.serial_port, baudrate=args.baudrate):
                controller['port'] = args.serial_port
                controller['baudrate'] = args.baudrate
                print(f"✓ Connected to serial port: {args.serial_port} @ {args.baudrate:,} baud")
            else:
                controller['servo'] = None
                print(f"❌ Failed to connect to serial port: {args.serial_port}")

    print("\n" + "="*50)
    print("  Feetech Servo Control - Web Interface")
    print("="*50)
    print(f"\n  Open your browser to: http://localhost:{args.port}")
    if args.serial_port and controller['port']:
        print(f"  Serial interface: {controller['port']} @ {controller['baudrate']:,} baud")
    print("\n  Press Ctrl+C to stop the server\n")
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
