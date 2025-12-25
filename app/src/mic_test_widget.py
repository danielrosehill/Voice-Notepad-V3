"""Microphone test widget for checking audio levels before recording."""

import math
import struct
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QGroupBox,
    QFrame,
    QProgressBar,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from .audio_recorder import AudioRecorder


class LevelMeter(QFrame):
    """A visual level meter widget."""

    def __init__(self, label: str = "", parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            "QFrame { background-color: #f8f9fa; border-radius: 6px; padding: 8px; }"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)

        # Label
        self.label = QLabel(label)
        self.label.setFixedWidth(50)
        self.label.setStyleSheet("font-weight: bold; color: #333;")
        layout.addWidget(self.label)

        # Progress bar as level meter
        self.meter = QProgressBar()
        self.meter.setRange(0, 100)
        self.meter.setValue(0)
        self.meter.setTextVisible(False)
        self.meter.setFixedHeight(20)
        self.meter.setStyleSheet(
            """
            QProgressBar {
                background-color: #e9ecef;
                border-radius: 4px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #28a745;
                border-radius: 4px;
            }
            """
        )
        layout.addWidget(self.meter, 1)

        # dB reading
        self.db_label = QLabel("-- dB")
        self.db_label.setFixedWidth(70)
        self.db_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.db_label.setStyleSheet("color: #666; font-family: monospace;")
        layout.addWidget(self.db_label)

    def set_level(self, db: float, is_clipping: bool = False):
        """Set the level in dB. Range is approximately -60 to 0 dB."""
        # Convert dB to percentage (0-100)
        # -60 dB = 0%, 0 dB = 100%
        percentage = max(0, min(100, (db + 60) / 60 * 100))
        self.meter.setValue(int(percentage))

        # Update dB display
        if db <= -60:
            self.db_label.setText("-- dB")
        else:
            self.db_label.setText(f"{db:.1f} dB")

        # Color based on level
        if is_clipping or db > -3:
            color = "#dc3545"  # Red - clipping
        elif db > -12:
            color = "#ffc107"  # Yellow - high
        elif db > -40:
            color = "#28a745"  # Green - good
        else:
            color = "#6c757d"  # Gray - too quiet

        self.meter.setStyleSheet(
            f"""
            QProgressBar {{
                background-color: #e9ecef;
                border-radius: 4px;
                border: none;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 4px;
            }}
            """
        )

    def reset(self):
        """Reset the meter to initial state."""
        self.meter.setValue(0)
        self.db_label.setText("-- dB")
        self.meter.setStyleSheet(
            """
            QProgressBar {
                background-color: #e9ecef;
                border-radius: 4px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #28a745;
                border-radius: 4px;
            }
            """
        )


class MicTestWidget(QWidget):
    """Widget for testing microphone levels."""

    TEST_DURATION = 4  # seconds

    def __init__(self, parent=None):
        super().__init__(parent)
        self.recorder: Optional[AudioRecorder] = None
        self.test_timer: Optional[QTimer] = None
        self.countdown_timer: Optional[QTimer] = None
        self.remaining_seconds = 0
        self.setup_ui()

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("Microphone Test")
        title.setFont(QFont("Sans", 16, QFont.Weight.Bold))
        main_layout.addWidget(title)

        desc = QLabel(
            "Test your microphone levels before recording to ensure optimal audio quality."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #666; font-size: 12px; margin-bottom: 8px;")
        main_layout.addWidget(desc)

        # Device selection
        device_group = QGroupBox("Microphone")
        device_layout = QVBoxLayout(device_group)

        device_row = QHBoxLayout()
        device_label = QLabel("Device:")
        device_label.setStyleSheet("font-weight: bold;")
        device_row.addWidget(device_label)

        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(300)
        self._populate_devices()
        device_row.addWidget(self.device_combo, 1)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setFixedWidth(80)
        refresh_btn.clicked.connect(self._populate_devices)
        refresh_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            """
        )
        device_row.addWidget(refresh_btn)

        device_layout.addLayout(device_row)
        main_layout.addWidget(device_group)

        # Test button and status
        test_group = QGroupBox("Test")
        test_layout = QVBoxLayout(test_group)

        self.test_btn = QPushButton(f"Test Microphone ({self.TEST_DURATION} seconds)")
        self.test_btn.setFixedHeight(45)
        self.test_btn.clicked.connect(self.start_test)
        self.test_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #007bff;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #0056b3;
            }
            QPushButton:disabled {
                background-color: #6c757d;
            }
            """
        )
        test_layout.addWidget(self.test_btn)

        self.status_label = QLabel("Click the button to start a 4-second test recording")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: #666; font-size: 12px; margin-top: 8px;")
        test_layout.addWidget(self.status_label)

        main_layout.addWidget(test_group)

        # Results section
        results_group = QGroupBox("Results")
        results_layout = QVBoxLayout(results_group)
        results_layout.setSpacing(12)

        # Level meters
        self.rms_meter = LevelMeter("RMS")
        results_layout.addWidget(self.rms_meter)

        self.peak_meter = LevelMeter("Peak")
        results_layout.addWidget(self.peak_meter)

        # Diagnosis container
        self.diagnosis_frame = QFrame()
        self.diagnosis_frame.setStyleSheet(
            """
            QFrame {
                background-color: #f8f9fa;
                border-radius: 8px;
                padding: 12px;
            }
            """
        )
        diagnosis_layout = QVBoxLayout(self.diagnosis_frame)
        diagnosis_layout.setSpacing(4)

        self.diagnosis_icon = QLabel("")
        self.diagnosis_icon.setStyleSheet("font-size: 20px;")
        diagnosis_layout.addWidget(self.diagnosis_icon)

        self.diagnosis_title = QLabel("No test results yet")
        self.diagnosis_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #333;")
        diagnosis_layout.addWidget(self.diagnosis_title)

        self.diagnosis_detail = QLabel(
            "Run a microphone test to check your audio levels."
        )
        self.diagnosis_detail.setWordWrap(True)
        self.diagnosis_detail.setStyleSheet("color: #666; font-size: 12px;")
        diagnosis_layout.addWidget(self.diagnosis_detail)

        results_layout.addWidget(self.diagnosis_frame)
        main_layout.addWidget(results_group)

        # Tips section
        tips_group = QGroupBox("Tips")
        tips_layout = QVBoxLayout(tips_group)

        tips = [
            "Speak at your normal volume during the test",
            "For speech, aim for RMS levels between -30 dB and -12 dB",
            "Avoid clipping (red) - reduce gain or move away from the mic",
            "If levels are too low, increase gain or move closer to the mic",
        ]

        for tip in tips:
            tip_label = QLabel(f"• {tip}")
            tip_label.setWordWrap(True)
            tip_label.setStyleSheet("color: #555; font-size: 11px;")
            tips_layout.addWidget(tip_label)

        main_layout.addWidget(tips_group)

        main_layout.addStretch()

    def _populate_devices(self):
        """Populate the device dropdown with available input devices."""
        self.device_combo.clear()
        self.device_combo.addItem("Default", None)

        # Create temporary recorder to get devices
        temp_recorder = AudioRecorder()
        devices = temp_recorder.get_input_devices()
        temp_recorder.cleanup()

        for idx, name in devices:
            self.device_combo.addItem(name, idx)

    def start_test(self):
        """Start the microphone test."""
        self.test_btn.setEnabled(False)
        self.device_combo.setEnabled(False)
        self.remaining_seconds = self.TEST_DURATION

        # Reset meters
        self.rms_meter.reset()
        self.peak_meter.reset()
        self._update_diagnosis("recording", "Recording...", "Speak normally during the test.")

        # Create recorder with selected device
        self.recorder = AudioRecorder()
        device_index = self.device_combo.currentData()
        if device_index is not None:
            self.recorder.set_device(device_index)

        # Start recording
        self.recorder.start_recording()
        self._update_countdown()

        # Countdown timer (updates every second)
        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(self._update_countdown)
        self.countdown_timer.start(1000)

        # Test completion timer
        self.test_timer = QTimer()
        self.test_timer.setSingleShot(True)
        self.test_timer.timeout.connect(self._complete_test)
        self.test_timer.start(self.TEST_DURATION * 1000)

    def _update_countdown(self):
        """Update the countdown display."""
        if self.remaining_seconds > 0:
            self.status_label.setText(
                f"Recording... {self.remaining_seconds} second{'s' if self.remaining_seconds != 1 else ''} remaining"
            )
            self.status_label.setStyleSheet(
                "color: #007bff; font-size: 12px; font-weight: bold; margin-top: 8px;"
            )
            self.remaining_seconds -= 1
        else:
            self.status_label.setText("Analyzing...")

    def _complete_test(self):
        """Complete the test and analyze results."""
        # Stop timers
        if self.countdown_timer:
            self.countdown_timer.stop()
            self.countdown_timer = None

        # Stop recording
        if self.recorder:
            self.recorder.stop_recording()

            # Analyze audio levels
            rms_db, peak_db, is_clipping = self._analyze_audio()

            # Update meters
            self.rms_meter.set_level(rms_db, is_clipping)
            self.peak_meter.set_level(peak_db, is_clipping)

            # Determine diagnosis
            self._set_diagnosis(rms_db, peak_db, is_clipping)

            # Cleanup
            self.recorder.cleanup()
            self.recorder = None

        # Re-enable controls
        self.test_btn.setEnabled(True)
        self.device_combo.setEnabled(True)
        self.status_label.setText("Test complete. Click to test again.")
        self.status_label.setStyleSheet("color: #28a745; font-size: 12px; margin-top: 8px;")

    def _analyze_audio(self) -> tuple[float, float, bool]:
        """Analyze recorded audio and return (rms_db, peak_db, is_clipping)."""
        if not self.recorder or not self.recorder.frames:
            return -60.0, -60.0, False

        # Collect all samples
        all_samples = []
        for frame_bytes in self.recorder.frames:
            # Unpack 16-bit signed samples
            num_samples = len(frame_bytes) // 2
            samples = struct.unpack(f"<{num_samples}h", frame_bytes)
            all_samples.extend(samples)

        if not all_samples:
            return -60.0, -60.0, False

        # Calculate RMS
        sum_squares = sum(s * s for s in all_samples)
        rms = math.sqrt(sum_squares / len(all_samples))

        # Calculate Peak
        peak = max(abs(s) for s in all_samples)

        # Check for clipping (samples near max value)
        max_value = 32767
        clipping_threshold = 32000  # ~98% of max
        is_clipping = peak >= clipping_threshold

        # Count how many samples are clipping
        clipping_count = sum(1 for s in all_samples if abs(s) >= clipping_threshold)
        clipping_percentage = clipping_count / len(all_samples) * 100

        # Convert to dB
        rms_db = 20 * math.log10(rms / max_value) if rms > 0 else -60.0
        peak_db = 20 * math.log10(peak / max_value) if peak > 0 else -60.0

        # Clamp to reasonable range
        rms_db = max(-60.0, rms_db)
        peak_db = max(-60.0, peak_db)

        return rms_db, peak_db, is_clipping

    def _set_diagnosis(self, rms_db: float, peak_db: float, is_clipping: bool):
        """Set the diagnosis based on audio levels."""
        if is_clipping or peak_db > -3:
            self._update_diagnosis(
                "error",
                "Audio is clipping",
                "Your audio is too loud and distorting. Reduce your microphone gain "
                "or move further from the microphone to avoid distortion in your recordings.",
            )
        elif rms_db > -12:
            self._update_diagnosis(
                "warning",
                "Audio is loud",
                "Your levels are on the high side. This may work fine, but consider "
                "reducing gain slightly if you experience any distortion.",
            )
        elif rms_db >= -30:
            self._update_diagnosis(
                "success",
                "Audio level is good",
                "Your microphone is recording at an optimal level. "
                "No adjustments needed.",
            )
        elif rms_db >= -40:
            self._update_diagnosis(
                "warning",
                "Audio is quiet",
                "Your levels are a bit low. Consider increasing your microphone gain "
                "or moving closer to the microphone for better clarity.",
            )
        else:
            self._update_diagnosis(
                "error",
                "Audio is too quiet",
                "Your audio levels are very low. Increase your microphone gain significantly, "
                "move much closer to the microphone, or check that the correct input device is selected.",
            )

    def _update_diagnosis(self, status: str, title: str, detail: str):
        """Update the diagnosis display."""
        self.diagnosis_title.setText(title)
        self.diagnosis_detail.setText(detail)

        if status == "success":
            self.diagnosis_frame.setStyleSheet(
                """
                QFrame {
                    background-color: #d4edda;
                    border: 1px solid #c3e6cb;
                    border-radius: 8px;
                    padding: 12px;
                }
                """
            )
            self.diagnosis_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #155724;")
            self.diagnosis_detail.setStyleSheet("color: #155724; font-size: 12px;")
        elif status == "warning":
            self.diagnosis_frame.setStyleSheet(
                """
                QFrame {
                    background-color: #fff3cd;
                    border: 1px solid #ffc107;
                    border-radius: 8px;
                    padding: 12px;
                }
                """
            )
            self.diagnosis_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #856404;")
            self.diagnosis_detail.setStyleSheet("color: #856404; font-size: 12px;")
        elif status == "error":
            self.diagnosis_frame.setStyleSheet(
                """
                QFrame {
                    background-color: #f8d7da;
                    border: 1px solid #f5c6cb;
                    border-radius: 8px;
                    padding: 12px;
                }
                """
            )
            self.diagnosis_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #721c24;")
            self.diagnosis_detail.setStyleSheet("color: #721c24; font-size: 12px;")
        else:  # recording or default
            self.diagnosis_frame.setStyleSheet(
                """
                QFrame {
                    background-color: #cce5ff;
                    border: 1px solid #b8daff;
                    border-radius: 8px;
                    padding: 12px;
                }
                """
            )
            self.diagnosis_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #004085;")
            self.diagnosis_detail.setStyleSheet("color: #004085; font-size: 12px;")
