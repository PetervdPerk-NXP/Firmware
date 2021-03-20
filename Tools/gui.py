#!/usr/bin/env python
############################################################################
#
#   Copyright (C) 2021 PX4 Development Team. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in
#    the documentation and/or other materials provided with the
#    distribution.
# 3. Neither the name PX4 nor the names of its contributors may be
#    used to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS
# OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED
# AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.
#
############################################################################


"""
gui.py:
PX4 pyside Qt GUI confgure to Kconfig and compile and flash boards

@author: Peter van der Perk <peter.vanderperk@nxp.com>
"""

import sys
import os
from pprint import pprint as pp

from PySide2.QtWidgets import QApplication, QWidget, QGridLayout, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSizePolicy, QTreeView, QGroupBox, QTextEdit
from PySide2.QtGui import QStandardItem, QStandardItemModel, QPixmap, QFont
from PySide2.QtCore import QFile, Qt, QProcessEnvironment, QProcess, QSortFilterProxyModel, QAbstractProxyModel
from PySide2.QtUiTools import QUiLoader

import kconfiglib
from kconfiglib import Kconfig, Symbol, Choice, MENU, COMMENT, MenuNode, \
                       BOOL, TRISTATE, STRING, INT, HEX, \
                       AND, OR

class KconfigFilterProxyModel(QSortFilterProxyModel):
    """
    Custom QSortFilterProxyModel that hides invisible kconfig symbols
    using Kconfiblib
    """
    def __init__(self, parent=None):
        super(KconfigFilterProxyModel, self).__init__(parent)

    def filterAcceptsRow(self, source_row, source_parent):
        symbol = self.sourceModel().index(source_row, 0, source_parent).data(Qt.UserRole)
        if isinstance(symbol, Symbol):
            if(symbol.visibility == 0):
                return False
        return True

class Kconfig():
    def __init__(self):
        env = QProcessEnvironment.systemEnvironment()
        self.defconfig_path = env.value('GUI_DEFCONFIG')
        self.kconf = kconfiglib.standard_kconfig(env.value('GUI_KCONFIG'))
        self.kconf.load_config(self.defconfig_path)

        self.model = QStandardItemModel()
        self.model.setRowCount(0)
        self.getItems(self.kconf.top_node.list, self.model.invisibleRootItem())

        self.kconfigProxyModel = KconfigFilterProxyModel()
        self.kconfigProxyModel.setSourceModel(self.model)

        self.model.itemChanged.connect(self.configChanged)

    def saveDefConfig(self):
        print(self.kconf.write_min_config(self.defconfig_path))

    def configChanged(self, field: QStandardItem):
        symbol = field.data(Qt.UserRole);
        if isinstance(symbol, Symbol):
            if(field.isCheckable()):
                if(field.checkState() == Qt.Checked):
                    symbol.set_value(2) # Why 2 though??
                else:
                    symbol.set_value(0) # Why 2 though??
            elif(field.isEditable()):
                if(symbol.set_value(field.text()) == False): # failed set back to orig_type
                    field.setText(symbol.str_value)

        self.kconfigProxyModel.invalidateFilter()

    def getModel(self):
        return self.kconfigProxyModel

    def indent_print(self, s):
        indent = 0
        print(indent*" " + s)

    def getItems(self, node, parent):
        while node:
            nodeItem = None
            if isinstance(node.item, Symbol):
                nodeItem = QStandardItem(node.prompt[0])
                nodeItem.setEditable(False)
                nodeValue = QStandardItem()

                if(node.item.orig_type == BOOL):
                    nodeItem.setCheckable(True)
                    if(node.item.user_value is not None):
                        nodeItem.setCheckState(Qt.Checked)
                elif(node.item.orig_type == TRISTATE):
                    nodeItem.setUserTristate(True)
                    if(node.item.user_value is not None): # FIXME tristate
                        nodeItem.setCheckState(Qt.Checked)
                else:
                    # Int string hex
                    nodeValue.setText(node.item.str_value)
                    nodeValue.setData(node.item, Qt.UserRole)

                parent.appendRow([nodeItem, nodeValue])
                nodeItem.setData(node.item.name, Qt.ToolTipRole)
                nodeItem.setData(node.item, Qt.UserRole)

            elif isinstance(node.item, Choice):
                #FIXME choice
                self.indent_print("FIXME choice")

            elif node.item == MENU:
                nodeItem = QStandardItem(node.prompt[0])
                nodeItem.setEditable(False)
                parent.appendRow([nodeItem, QStandardItem()])
                nodeItem.setData(node.item, Qt.UserRole) # Menu are always visible
                self.indent_print('menu "{}"'.format(node.prompt[0]))

            if node.list:
                if(nodeItem is not None):
                    self.getItems(node.list, nodeItem)
                else:
                    print("FIXME unparsed Kconfig")

            node = node.next

class PX4DevGUI(QWidget):

    FROM, SUBJECT, DATE = range(3)
    taskRunning = False

    def __init__(self):
        super().__init__()
        env = QProcessEnvironment.systemEnvironment()
        self.config = env.value('CONFIG')

        layoutGrid = QGridLayout()
        self.setLayout(layoutGrid)

        # Board info name, platform target
        boardInfoLayout = QHBoxLayout()
        layoutGrid.addLayout(boardInfoLayout, 0, 0)

        boardInfoLabel = QLabel("%s %s\n"
                                "Label: %s\n"
                                "Platform: %s\n"
                                "%s\n"
                                "Architecture: %s\n"
                                "Romfsroot: %s\n"
                                % (env.value('VENDOR'),env.value('MODEL'),env.value('LABEL'),
                                   env.value('PLATFORM'),env.value('TOOLCHAIN'),
                                   env.value('ARCHITECTURE'),env.value('ROMFSROOT')));
        boardImageLabel = QLabel('Insert board image here');
        boardPixmap = QPixmap("Tools/" + self.config + ".png") #FIXME proper way to store board images
        boardImageLabel.setPixmap(boardPixmap)
        boardImageLabel.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter);

        boardInfoLayout.addWidget(boardInfoLabel)
        boardInfoLayout.addWidget(boardImageLabel)

        # Kconfiglib based configuration options
        self.dataGroupBox = QGroupBox("configuration")
        self.dataView = QTreeView(self)
        self.dataView.setHeaderHidden(True)

        dataLayout = QHBoxLayout()
        dataLayout.addWidget(self.dataView)
        self.dataGroupBox.setLayout(dataLayout)

        self.kconfig = Kconfig()
        self.dataView.setModel(self.kconfig.getModel())
        self.dataView.expanded.connect(lambda: self.dataView.resizeColumnToContents(0))
        self.dataView.resizeColumnToContents(0);

        kconfigLayout = QVBoxLayout()
        kconfigLayout.addWidget(self.dataGroupBox)
        layoutGrid.addLayout(kconfigLayout, 1, 0)

        # CMake output
        self.terminalGroupBox = QGroupBox("Terminal output")
        self.terminalOutput = QTextEdit()
        f = QFont("unexistent")
        f.setStyleHint(QFont.Monospace);
        self.terminalOutput.setFont(f);
        self.terminalOutput.setReadOnly(True)

        terminalLayout = QHBoxLayout()
        terminalLayout.addWidget(self.terminalOutput)
        self.terminalGroupBox.setLayout(terminalLayout)

        terminalLayout = QVBoxLayout()
        terminalLayout.addWidget(self.terminalGroupBox)
        layoutGrid.addLayout(terminalLayout, 2, 0)

        # GUI actions configure, compile & flash
        actionLayout = QHBoxLayout()
        layoutGrid.addLayout(actionLayout, 3, 0)

        actionConfigure = QPushButton('Configure');
        actionConfigure.clicked.connect(lambda: self.configureClick())
        actionCompile = QPushButton('Compile');
        actionCompile.clicked.connect(lambda: self.compileClick())
        actionFlash = QPushButton('Flash');
        actionFlash.clicked.connect(lambda: self.flashClick())
        px4Logo = QLabel('PX4 Logo');
        px4logopixmap = QPixmap('Tools/PX4-Logo-Black.png')
        px4Logo.setPixmap(px4logopixmap)
        px4Logo.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter);

        actionLayout.addWidget(actionConfigure)
        actionLayout.addWidget(actionCompile)
        actionLayout.addWidget(actionFlash)
        actionLayout.addWidget(px4Logo)

    def taskFinished(self):
        print("Task done") # Make a loading circle and process return status??
        self.taskRunning = False;

    def configureClick(self):
        print("configureClick")
        self.kconfig.saveDefConfig()

        if(self.taskRunning == False):
            self.taskRunning = True;

            program = "make"
            arguments = [self.config, "clean"]

            self.myProcess = QProcess()
            self.myProcess.start(program, arguments)
            self.myProcess.setProcessEnvironment(QProcessEnvironment.systemEnvironment())
            self.myProcess.readyReadStandardOutput.connect(self.write_terminal_output)
            self.myProcess.finished.connect(self.taskFinished)

    def compileClick(self):
        print("compileClick")
        if(self.taskRunning == False):
            self.taskRunning = True;

            program = "make"
            arguments = [self.config]

            self.myProcess = QProcess()
            self.myProcess.start(program, arguments)
            self.myProcess.setProcessEnvironment(QProcessEnvironment.systemEnvironment())
            self.myProcess.readyReadStandardOutput.connect(self.write_terminal_output)
            self.myProcess.finished.connect(self.taskFinished)

    def flashClick(self):
        print("flashClick")
        if(self.taskRunning == False):
            self.taskRunning = True;

            program = "make"
            arguments = [self.config, "upload"]

            self.myProcess = QProcess()
            self.myProcess.start(program, arguments)
            self.myProcess.setProcessEnvironment(QProcessEnvironment.systemEnvironment())
            self.myProcess.readyReadStandardOutput.connect(self.write_terminal_output)
            self.myProcess.finished.connect(self.taskFinished)

    def write_terminal_output(self):
        self.terminalOutput.append(self.myProcess.readAllStandardOutput().data().decode())

def main():
    app = QApplication(sys.argv)
    demo = PX4DevGUI()
    demo.show()
    sys.exit(app.exec_())

main()
