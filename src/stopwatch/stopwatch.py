#!/usr/bin/env python3

import typing
from PyQt5 import uic
from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import *
import PyQt5.QtWidgets as qw

from std_msgs.msg import *
import rospy

import paho.mqtt.client as mqtt
import time, json, os
from collections import defaultdict
from datetime import datetime
from importlib import import_module
from typing import *

class QHSeparationLine(qw.QFrame):
  '''
  a horizontal separation line\n
  '''
  def __init__(self):
    super().__init__()
    self.setMinimumWidth(1)
    self.setFixedHeight(20)
    self.setFrameShape(qw.QFrame.HLine)
    self.setFrameShadow(qw.QFrame.Sunken)
    self.setSizePolicy(qw.QSizePolicy.Preferred, qw.QSizePolicy.Minimum)

    # self.setPalette(palette)
    return
  
def SaveFile(data:json, path:str, filename:str):
    with open(path + '/' + filename+ '.json', 'w') as file:
        json.dump(data, file)

class SubscriberThread(QThread):
    flag = pyqtSignal(int)
    def __init__(self, message_type:str='ros', host:str='localhost'):
        QThread.__init__(self)
        self.message_type   = message_type
        self.host           = host
        self.mqtt_port      = 1883

        self.topic          = '/stopwatch'
        self.client_name    = 'stopwatch'
        self.__running      = True
        self.create_subscriber()

    def create_subscriber(self):
        if self.message_type == 'ros':
            # Create ros node and ros subscriber
            rospy.init_node(self.client_name, anonymous=True)
            self.ros_rate   = rospy.Rate(1000)
            self.subscriber = rospy.Subscriber(self.topic, Int32, self._callback)
        
        elif self.message_type == 'mqtt':
            print(self.host)
            self.subscriber = mqtt.Client(self.client_name)
            self.subscriber.connect(self.host, self.mqtt_port)
            self.subscriber.subscribe(self.topic)
            self.subscriber.on_message = self.on_message

    def _callback(self, message):
        self.flag.emit(message.data)

    def on_message(self, client, userdata, message):
        self.flag.emit(int(message.payload.decode('utf-8')))
    
    def run(self):
        if self.message_type == 'ros':
            while self.__running:
                self.ros_rate.sleep()
        else:
            self.subscriber.loop_start()

    def stop(self):
        if self.message_type == 'ros':
            self.__running = False
        else:
            self.subscriber.loop_stop()
            self.client.disconnect()
        # self.terminate()

class HostIP(qw.QMainWindow):
    host_ip = pyqtSignal(str)
    def __init__(self, PATH:str):
        super(HostIP, self).__init__()
        self.PATH   = PATH
        uic.loadUi(self.PATH + '/src/stopwatch/host_setting.ui', self)

        # Get variables in UI
        self.textbox_host_ip    = self.findChild(qw.QLineEdit, 'lineEdit_host_ip')
        print(self.textbox_host_ip)
        self.textbox_host_ip.editingFinished.connect(self._send_host_ip)

    def _send_host_ip(self):
        host_ip = self.textbox_host_ip.text()
        self.host_ip.emit(host_ip)

class StopWatch(qw.QMainWindow):
    def __init__(self, parent=None):
        super(StopWatch, self).__init__()

        # Find the current directory
        self.PATH           = os.getcwd()

        # Load the UI Page
        uic.loadUi(self.PATH + '/src/stopwatch/stopwatch.ui', self)

        # Difine variables     
        self.con            = 0 
        self.mode           = 'manual'   
        self.HOST_IP        = 'localhost'
        self.SUBSCRIBER_MSG_TYPE    = ['ros', 'mqtt']

        self.COLOR_LST      = ['#6861FF', '#AA0DFD', '#DA00EB', '#FE9010', '#00FF53', '#01EBD0', '#00E9CE']
        self.color_count    = 0

        self.TIME_TYPE      = ['time', 'unix']
        self.LAB_DISPLAYS   = ['lab', 'time', 'unix']
        self.stopwatch_time = 0
        self.unix_time      = 0
        self.lab_time       = 0
        self.event_name     = None

        self.__start        = False   
        self.__reset        = True
        self.recorded_time  = defaultdict(lambda: defaultdict(dict))
        self.start_time     = None

        self.FILENAME       = 'stopwatch'
        self.file_count     = 0
        self.save_path      = None


        # Get button variables in ui ================================================================================
        self.button     = dict()
        for name in ['start', 'lab', 'reset']:
            self.button[name]   = self.findChild(qw.QPushButton, 'button_' + name)

            # Toggle button 
            self.button[name].clicked.connect(lambda state, button_name=name: self._press_button(button_name))

        self.button['lab'].setDisabled(True)

         # Get label variables in ui =================================================================================
        self.label      = dict()
        for name in ['current_date', 'recorded_date', 'unix']:
            self.label[name]    = self.findChild(qw.QLabel, 'label_' + name)
        
        self.lcd        = dict()
        for lcd_display in self.TIME_TYPE:
            self.lcd[lcd_display]   = self.findChild(qw.QLCDNumber, 'lcd_' + lcd_display)
            self.lcd[lcd_display]   = self._config_lcd(self.lcd[lcd_display], lcd_display)
       

        # Get and hide layout of lab widget ==========================================================================
        self.event_count        = 0
        self.layout_lab         = dict()
        
        self.layout_lab['widget']   = self.findChild(qw.QWidget, 'widget')
        self.layout_lab['layout']   = self.findChild(qw.QVBoxLayout, 'layout_lab')

        self._get_reference_lab()
        # hide the lab widget
        self.layout_lab['widget'].hide()

        # Get Menubar variables =======================================================================================
        self.menubar_qt     = dict()
        for name in ['Save', 'Save_As', 'Host_name', 'Clear']:
            self.menubar_qt[name] = self.findChild(qw.QAction, 'action' + name)
            if name == 'Host_name':
                self.menubar_qt[name].triggered.connect(self._open_host_ip_window)
            elif name == 'Clear':
                self.menubar_qt[name].triggered.connect(self._clear_recorded_time_data)
            else:
                self.menubar_qt[name].triggered.connect(lambda state, menu=name: self._click_save_file(menu))

        
        # Get automode variables =======================================================================================
        self.auto_qt    = dict()
        self.auto_qt['checkbox']    = self.findChild(qw.QCheckBox, 'cb_flag')
        self.auto_qt['comboBox']    = self.findChild(qw.QComboBox, 'comboBox_message')
        self.auto_qt['comboBox'].currentTextChanged.connect(self._build_subscriber)

        # Create timer ===============================================================================================
        self.timer  = dict()
        self._start_timer('unix', self._update_time, 1)
        
        self.show()

    def _get_reference_lab(self):
        # Create the located lab variables
        self.layout_lab['lab']      = defaultdict(lambda: defaultdict(dict))

        self.layout_lab['lab']['ref']['widget']    = self.findChild(qw.QWidget, 'widget_2')
        self.layout_lab['lab']['ref']['label']     = self.findChild(qw.QLabel, 'label_lab_time')
        self.layout_lab['lab']['ref']['lcd_lab']       = self.findChild(qw.QLCDNumber, 'lcd_lab_lab')
        self.layout_lab['lab']['ref']['lcd_lab']       = self._config_lcd(self.layout_lab['lab']['ref']['lcd_lab'], 'time')
        self.layout_lab['lab']['ref']['lcd_time']       = self.findChild(qw.QLCDNumber, 'lcd_lab_time')
        self.layout_lab['lab']['ref']['lcd_time']       = self._config_lcd(self.layout_lab['lab']['ref']['lcd_time'], 'time')
        self.layout_lab['lab']['ref']['lcd_unix']       = self.findChild(qw.QLCDNumber, 'lcd_lab_unix')
        self.layout_lab['lab']['ref']['lcd_unix']       = self._config_lcd(self.layout_lab['lab']['ref']['lcd_unix'], 'unix')

        # Hide the reference lab
        self.layout_lab['lab']['ref']['widget'].hide()

    @pyqtSlot(str)
    def _get_host_ip(self, host_ip):
        self.HOST_IP = host_ip
        print(self.HOST_IP)

    def _open_host_ip_window(self):
        self.host_ip_window = HostIP(self.PATH)
        self.host_ip_window.host_ip.connect(self._get_host_ip)
        self.host_ip_window.show()

    def _build_subscriber(self):
        if self.auto_qt['comboBox'].currentText() == 'ROS message':
            self.mode = 'ros'
        elif self.auto_qt['comboBox'].currentText() == 'MQTT message':
            self.mode = 'mqtt'
        print(self.mode)
        self.subscriber  = SubscriberThread(self.mode, self.HOST_IP)
        self.subscriber.flag.connect(self._toggle_button)
        self.subscriber.start()

    @pyqtSlot(int)
    def _toggle_button(self, flag):
        if flag == 1:
            self._press_button('start')
        elif flag == 2:
            self._press_button('lab')
        elif flag == 3:
            self._press_button('reset')
        elif flag == 4:
            self._save_file()

    def _config_lcd(self, lcd:object, lcd_type:str, digital_count=None) -> object:

        time_display = '00:00.000' if lcd_type == 'time' else int(time.time())
        digital_count = digital_count or (9 if lcd_type == 'time' else 10)

        lcd.setDigitCount(digital_count)    
        lcd.setSegmentStyle(qw.QLCDNumber.Flat)
        lcd.display(time_display)

        return lcd


    def _update_time(self):
        
        
        timeDisplay     = datetime.now()
        self.unix_time  = timeDisplay.timestamp()

        # self.label['current_date'].setText(str(self.unix_time))
        self.label['current_date'].setText(str(timeDisplay.strftime("%Y-%m-%d %H:%M:%S")))   
        self.lcd['unix'].display(int(self.unix_time))
       
        if self.__start:
            # Update the time and display it in lcd
            self.stopwatch_time         += 1
            self.lab_time               += 1
            self.lcd['time'].display(self.convert())
            self.layout_lab['lab'][self.event_name]['lcd_lab'].display(self.convert('lab'))
        else:
            self.label['recorded_date'].setText(str(timeDisplay.strftime("%Y-%m-%d %H:%M:%S")))
        
    
    def convert(self, duration:str='all') -> str:
        if duration == 'all':
            milliseconds    = self.stopwatch_time % 1000
            seconds         = int(self.stopwatch_time / 1000) % 60
            minutes         = int(self.stopwatch_time / (1000 * 60)) % 60

        else:
            milliseconds    = self.lab_time % 1000
            seconds         = int(self.lab_time / 1000) % 60
            minutes         = int(self.lab_time / (1000 * 60)) % 60

        stopwatch_time = "{:02d}:{:02d}:{:03d}".format(minutes, seconds, milliseconds)

        return stopwatch_time
    
    def _update_captured_time(self, stopwatch_time:str, unix_time:int) -> None:

        for time_type, text_display in zip(self.TIME_TYPE, [stopwatch_time, unix_time]):
            # Collect variables
            self.recorded_time[self.start_time][self.event_name][time_type] = text_display
            # Display it in lcd
            self.layout_lab['lab'][self.event_name]['lcd_' + time_type].display(text_display)

    
    def _start_timer(self, name:str, function, time_interval=1):
        self.timer[name] = QtCore.QTimer()
        self.timer[name].setInterval(time_interval)
        self.timer[name].timeout.connect(function)
        self.timer[name].start()

    
    def _duplicate_object(self, obj:None, qt_class, time_type:str=None, stage:str=None) -> object:
        palette     = obj.palette()
        new_obj     = qt_class(obj)
        if qt_class.__name__ == 'QLCDNumber':
            if time_type == 'time':
                new_obj = self._config_lcd(new_obj, 'time')
            else:
                new_obj = self._config_lcd(new_obj, 'unix', 17)
            # new_obj.setMaximumHeight(25)
        else:
            if stage == 'init':
                new_obj.setText('Start')
            elif stage == 'continue':
                new_obj.setText('Start_' + str(self.con))
            else:
                new_obj.setText('Event_' + str(self.event_count))

            font = QtGui.QFont()
            font.setPointSize(16)
            font.setFamily(obj.font().family())
            new_obj.setFont(font)
        
        
        palette.setColor(QtGui.QPalette.Text, QtGui.QColor('#00FFFE'))
        palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor('#00FFFE'))
        new_obj.setPalette(palette)

        return new_obj
    
    def _change_lab_color(self):
        palette = self.layout_lab['lab'][self.event_name]['lcd_lab'].palette()
        palette.setColor(QtGui.QPalette.Text, QtGui.QColor(self.COLOR_LST[self.color_count]))
        palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(self.COLOR_LST[self.color_count]))
        self.layout_lab['lab'][self.event_name]['lcd_lab'].setPalette(palette)
    
    def _duplicate_lab(self, stage:str):

        if stage == 'init':         
            self.event_name = 'init'
        elif stage == 'continue':   
            self.event_name = 'start_' + str(self.con)
            self.con += 1
        else:
            self.event_name     = 'event_' + str(self.event_count)
            self.event_count    += 1

        # Create layout for label and lcd to show the lab time
        self.layout_lab['lab'][self.event_name]['layout']      = qw.QHBoxLayout()

                
        for qt_class, var_name in zip([qw.QLabel, qw.QLCDNumber], ['label', 'lcd']):
            ref_var = self.layout_lab['lab']['ref']

            time_displays = self.LAB_DISPLAYS if qt_class is qw.QLCDNumber else [None]
            time_types = ['time', 'time', 'unix'] if qt_class is qw.QLCDNumber else [None]

            for time_display, time_type in zip(time_displays, time_types):
                subname = var_name + ('_' + time_display if time_display else '')
                self.layout_lab['lab'][self.event_name][subname] = self._duplicate_object(obj=ref_var[subname],
                                                                                qt_class=qt_class,
                                                                                time_type=time_type, stage=stage)
        self._change_lab_color()

                
        # Add widget in lab layout
        for obj, obj_name in zip([qw.QLabel, qw.QLCDNumber], ['label', 'lcd']):
            if obj_name == 'lcd':
                [self.layout_lab['lab'][self.event_name]['layout'].addWidget(self.layout_lab['lab'][self.event_name]['lcd_' + x]) for x in self.LAB_DISPLAYS]
            else:
                self.layout_lab['lab'][self.event_name]['layout'].addWidget(self.layout_lab['lab'][self.event_name][obj_name])
        
        line = QHSeparationLine()
        
        # Create and set size of widget
        widget = qw.QWidget()
        widget.setMinimumHeight(50)
        widget.setMaximumHeight(50)
        widget.setLayout(self.layout_lab['lab'][self.event_name]['layout'])

        self.layout_lab['layout'].insertWidget(0, widget)
        # self.layout_lab['layout'].addWidget(line)
        
        if stage == 'init':
            # Set the initial time
            self.start_time = datetime.now().timestamp()
            self._update_captured_time('00:00.000', self.start_time)
        else:
            self._update_captured_time(self.convert(), self.unix_time)

        # Color counter
        if self.color_count == len(self.COLOR_LST)-1:
            self.color_count = 0
        else:
            self.color_count += 1

    def _clearLayout(self, layout):
        if layout is not None:
            while layout.count():
                item = layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    self._clearLayout(item.layout())  
    
    def _clear_lab_layout(self):
        for layout_name in list(self.layout_lab['lab'].keys()):
            if layout_name != 'ref':
                self._clearLayout(self.layout_lab['lab'][layout_name]['layout'])

                del self.layout_lab['lab'][layout_name]
        # Clear main layout
        self._clearLayout(self.layout_lab['layout'])
        # self.adjustSize()

    
    def _press_button(self, stage):
        # Get the color of button
        palette = self.lcd['time'].palette()
        if stage == 'start':
            # Stop timer
            if self.button['start'].text() == '&Stop':
                # Stop timer
                self.__start    = False

                # Collect the duration of previous lab
                self.recorded_time[self.start_time][self.event_name]['duration'] = self.convert('lab')
                self.lab_time   = 0

                # Edit the text of button
                self.button['start'].setText('&Start')
                # Change the color of button
                color = '#00FFFE'

                # Disable the lab button and enable the reset button
                self.button['lab'].setDisabled(True)
                self.button['reset'].setEnabled(True)
            
            # Start timer
            else:

                # Edit the text of button
                self.button['start'].setText('&Stop')
                
                # Chnage the color of button
                color = '#FF1818'

                # Enable the lab button and disable the reset button 
                self.button['reset'].setDisabled(True)
                self.button['lab'].setEnabled(True)

                

                # Start timer
                if self.__reset:
                    # Show the lab widget
                    self.layout_lab['widget'].show() 
                    # Create the first lab
                    self._duplicate_lab(stage='init')

                    self.label['recorded_date'].setText(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

                    self.__start = True
                    self.__reset = False
                else:
                    self._duplicate_lab(stage='continue')

                    self.__start = True
                

            # Change the text color of the start button
            palette = self._set_button_color(palette, color)
            self.button['start'].setPalette(palette)

        elif stage == 'reset':
            # Stop to use stopwatch
            self.__start            = False
            self.__reset            = True

            # Change the color of button
            palette = self._set_button_color(palette, '#00FFFE')
            self.button['start'].setPalette(palette)

            #  Collect the duration of previous lab
            self.recorded_time[self.start_time]['all'] = self.convert()

            # Change the text color of the start button
            self.button['start'].setText('&Start')
            self.button['reset'].setDisabled(True)

        
            # Clear the whole time lab
            self._clear_lab_layout()

            # Clear the recorded date text and change the lcd display
            self.lcd['time'].display('00:00.000')
            self.label['recorded_date'].setText('')

            # Clear variables
            self.stopwatch_time     = 0
            self.event_count        = 0
            self.color_count        = 0


        elif stage == 'lab':
            # Collect the duration of previous lab
            self.recorded_time[self.start_time][self.event_name]['duration'] = self.convert('lab')

            # Duplicate the lab widget
            self._duplicate_lab(stage='lab')
            self.lab_time = 0


    
    def _set_button_color(self, palette, color):
        palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(color))
        palette.setColor(QtGui.QPalette.Window, QtGui.QColor(color))
        return palette
    
    def _clear_recorded_time_data(self):
        del self.recorded_time
        # Reset the recorded time
        self.recorded_time = defaultdict(lambda: defaultdict(dict))
    
    def _browse_location_path(self):
        directory = qw.QFileDialog.getExistingDirectory(self, 'Select Directory')
        if directory != '':
            self.save_path = directory

    
    def _click_save_file(self, name):
        if name == 'Save_As':
            # Open the file dialog
            self._browse_location_path()

        self._save_file()
    
    def _save_file(self):
        directory   = self.save_path
        filename    = self.FILENAME

        if self.file_count != 0:
            filename = filename + str(self.file_count)
        elif any(self.mode == msg for msg in self.SUBSCRIBER_MSG_TYPE) and directory == None:
            directory = self.PATH + '/src/stopwatch/data'
            filename  = filename + '_' + self.mode

        print(directory, filename)
        SaveFile(self.recorded_time, directory, filename=filename)

        self.file_count += 1
    

if __name__ == '__main__':

    app = qw.QApplication(sys.argv)
    # Set to fusion style that it allow palette to work
    app.setStyle('Fusion')
    ex = StopWatch()
    sys.exit(app.exec_())