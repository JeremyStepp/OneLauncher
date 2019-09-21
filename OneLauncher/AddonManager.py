# coding=utf-8
###########################################################################
# Main window for OneLauncher.
#
# Based on PyLotRO
# (C) 2009 AJackson <ajackson@bcs.org.uk>
#
# Based on LotROLinux
# (C) 2007-2008 AJackson <ajackson@bcs.org.uk>
#
#
# (C) 2019 Jeremy Stepp <jeremy@bluetecno.com>
#
# This file is part of OneLauncher
#
# OneLauncher is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# OneLauncher is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with OneLauncher.  If not, see <http://www.gnu.org/licenses/>.
###########################################################################
from qtpy import QtCore, QtGui, QtWidgets, uic
import os
from pkg_resources import resource_filename
from glob import glob
from xml.dom import EMPTY_NAMESPACE
import xml.dom.minidom
from .OneLauncherUtils import GetText
import sqlite3
from shutil import rmtree


class AddonManager:
    # ID is from the order plugins are found on the filesystem. InterfaceID is the unique ID for plugins on lotrointerface.com
    COLUMN_LIST = [
        "ID",
        "Name",
        "Category",
        "Version",
        "Author",
        "Modified",
        "File",
        "InterfaceID",
        "Dependencies",
    ]

    def __init__(self, currentGame, osType, settingsDir, parent):
        self.settingsDir = settingsDir
        self.currentGame = currentGame
        self.parent = parent

        self.winAddonManager = QtWidgets.QDialog(parent, QtCore.Qt.FramelessWindowHint)

        uifile = resource_filename(__name__, "ui" + os.sep + "winAddonManager.ui")

        Ui_dlgAddonManager, base_class = uic.loadUiType(uifile)
        self.uiAddonManager = Ui_dlgAddonManager()
        self.uiAddonManager.setupUi(self.winAddonManager)

        self.uiAddonManager.btnBox.rejected.connect(self.btnBoxActivated)

        self.uiAddonManager.btnAddonsMenu = QtWidgets.QMenu()
        self.uiAddonManager.btnAddonsMenu.addAction(
            self.uiAddonManager.actionAddonImport
        )
        self.uiAddonManager.actionAddonImport.triggered.connect(
            self.actionAddonImportSelected
        )
        self.uiAddonManager.btnAddons.setMenu(self.uiAddonManager.btnAddonsMenu)
        self.uiAddonManager.btnAddons.clicked.connect(self.btnAddonsClicked)
        self.uiAddonManager.tabWidget.currentChanged.connect(self.tabWidgetIndexChanged)

        self.uiAddonManager.txtLog.hide()
        self.uiAddonManager.btnLog.clicked.connect(self.btnLogClicked)

        self.uiAddonManager.txtSearchBar.setFocus()
        self.uiAddonManager.txtSearchBar.textChanged.connect(
            self.txtSearchBarTextChanged
        )

        # Hides ID column
        self.uiAddonManager.tablePluginsInstalled.hideColumn(0)

        self.openDB()

        if osType.usingWindows:
            documents_folder = "My Documents"
        else:
            documents_folder = "Documents"

        if currentGame.startswith("DDO"):
            # Removes plugin and music tabs when using DDO
            self.uiAddonManager.tabWidgetFindMore.removeTab(0)
            self.uiAddonManager.tabWidgetFindMore.removeTab(1)
            self.uiAddonManager.tabWidgetInstalled.removeTab(0)
            self.uiAddonManager.tabWidgetInstalled.removeTab(1)

            self.data_folder = os.path.join(
                os.path.expanduser("~"), documents_folder, "Dungeons and Dragons Online"
            )
            # self.getInstalledThemes(data_folder)

        else:
            self.data_folder = os.path.join(
                os.path.expanduser("~"),
                documents_folder,
                "The Lord of the Rings Online",
            )

            self.getInstalledPlugins()
            # self.getInstalledThemes()
            # self.getInstalledMusic()

    def getInstalledPlugins(self):
        self.uiAddonManager.txtSearchBar.clear()

        data_folder = os.path.join(self.data_folder, "Plugins")
        os.makedirs(data_folder, exist_ok=True)

        # Finds all plugins and adds their .plugincompendium files to a list
        plugins_list_compendium = []
        plugins_list = []
        for folder in glob(os.path.join(data_folder, "*", "")):
            for file in os.listdir(folder):
                if file.endswith(".plugincompendium"):
                    plugins_list_compendium.append(os.path.join(folder, file))
                elif file.endswith(".plugin"):
                    plugins_list.append(os.path.join(folder, file))

        # Remove managed plugins from plugins list
        for plugin in plugins_list_compendium:
            doc = xml.dom.minidom.parse(plugin)
            nodes = doc.getElementsByTagName("Descriptors")[0].childNodes

            for node in nodes:
                item = QtWidgets.QTableWidgetItem()

                if node.nodeName == "descriptor":
                    try:
                        plugins_list.remove(
                            os.path.join(
                                data_folder,
                                (GetText(node.childNodes).replace("\\", os.sep)),
                            )
                        )
                    except ValueError:
                        self.addLog(plugin + " has misconfigured descriptors")

        self.addInstalledPluginstoDB(plugins_list, plugins_list_compendium)

    def addInstalledPluginstoDB(self, plugins_list, plugins_list_compendium):
        # Clears rows from db table
        self.c.execute("DELETE FROM tablePluginsInstalled")

        for plugin in plugins_list_compendium + plugins_list:
            items_row = [""] * (len(self.COLUMN_LIST) - 1)

            doc = xml.dom.minidom.parse(plugin)

            # Sets tag for plugin file xml search and category for unmanaged plugins
            if plugin.endswith(".plugincompendium"):
                dependencies = ""
                if doc.getElementsByTagName("Dependencies"):
                    nodes = doc.getElementsByTagName("Dependencies")[0].childNodes
                    for node in nodes:
                        if node.nodeName == "dependency":
                            dependencies = (
                                dependencies + "," + (GetText(node.childNodes))
                            )
                items_row[7] = dependencies[1:]

                tag = "PluginConfig"
            else:
                tag = "Information"
                items_row[1] = "Unmanaged"

            nodes = doc.getElementsByTagName(tag)[0].childNodes
            for node in nodes:
                if node.nodeName == "Name":
                    items_row[0] = GetText(node.childNodes)
                elif node.nodeName == "Author":
                    items_row[3] = GetText(node.childNodes)
                elif node.nodeName == "Version":
                    items_row[2] = GetText(node.childNodes)
                elif node.nodeName == "Id":
                    items_row[6] = GetText(node.childNodes)
            items_row[5] = plugin

            self.addRowToDB("tablePluginsInstalled", items_row)

        # Populate user visible table
        self.searchDB(self.uiAddonManager.tablePluginsInstalled, "")

    def openDB(self):
        table_list = [
            "tablePluginsInstalled",
            "tableThemesInstalled",
            "tableMusicInstalled",
            "tablePlugins",
            "tableThemes",
            "tableMusic",
            "tableThemesDDO",
            "tableThemesDDOInstalled",
        ]

        # Connects to addons_cache database and creates it if it does not exist
        if not os.path.exists(os.path.join(self.settingsDir, "addons_cache.sqlite")):
            self.conn = sqlite3.connect(
                os.path.join(self.settingsDir, "addons_cache.sqlite")
            )
            self.c = self.conn.cursor()

            for table in table_list:
                self.c.execute(
                    "CREATE VIRTUAL TABLE {tbl_nm} USING FTS5({clmA}, {clmB}, {clmC}, {clmD}, {clmE}, {clmF}, {clmG}, {clmH})".format(
                        tbl_nm=table,
                        clmA=self.COLUMN_LIST[1],
                        clmB=self.COLUMN_LIST[2],
                        clmC=self.COLUMN_LIST[3],
                        clmD=self.COLUMN_LIST[4],
                        clmE=self.COLUMN_LIST[5],
                        clmF=self.COLUMN_LIST[6],
                        clmG=self.COLUMN_LIST[7],
                        clmH=self.COLUMN_LIST[8],
                    )
                )
        else:
            self.conn = sqlite3.connect(
                os.path.join(self.settingsDir, "addons_cache.sqlite")
            )
            self.c = self.conn.cursor()

    def closeDB(self):
        self.conn.commit()
        self.conn.close()

    # def getInstalledThemes(self, data_folder):
    #     pass

    # def getInstalledMusic(self, data_folder):
    #     pass

    def actionAddonImportSelected(self):
        filenames = QtWidgets.QFileDialog.getOpenFileNames(
            self.winAddonManager,
            "Addon Files/Archives",
            os.path.expanduser("~"),
            "*.zip *.abc",
        )

        if filenames:
            for file in filenames:
                print(file)

    def txtSearchBarTextChanged(self, text):
        if self.currentGame.startswith("LOTRO"):
            # If in Installed tab
            if self.uiAddonManager.tabWidget.currentIndex() == 0:
                # If in PluginsInstalled tab
                if self.uiAddonManager.tabWidgetInstalled.currentIndex() == 0:
                    self.searchDB(self.uiAddonManager.tablePluginsInstalled, text)

    def searchDB(self, table, text):
        table.clearContents()
        table.setRowCount(0)

        if text:
            for word in text.split():
                search_word = "%" + word + "%"

                for row in self.c.execute(
                    "SELECT rowid, * FROM {table} WHERE Author LIKE ? OR Category LIKE ? OR Name LIKE ?".format(
                        table=table.objectName()
                    ),
                    (search_word, search_word, search_word),
                ):
                    # Detects duplicates from multi-word search
                    duplicate = False
                    for item in table.findItems(row[1], QtCore.Qt.MatchExactly):
                        if int((table.item(item.row(), 0)).text()) == row[0]:
                            duplicate = True
                            break
                    if not duplicate:
                        self.addRowToTable(table, row)
        else:
            # Shows all plugins if the search bar is empty
            for row in self.c.execute(
                "SELECT rowid, * FROM {table}".format(table=table.objectName())
            ):
                self.addRowToTable(table, row)

    # Adds row to a visible table. First value in list is row name
    def addRowToTable(self, table, list):
        table.setSortingEnabled(False)

        rows = table.rowCount()
        table.setRowCount(rows + 1)

        # Sets row name
        tbl_item = QtWidgets.QTableWidgetItem()
        tbl_item.setText(str(list[0]))

        # Adds items to row
        for i, item in enumerate(list):
            tbl_item = QtWidgets.QTableWidgetItem()

            tbl_item.setText(str(item))
            # Sets color to red if plugin is unmanaged
            if item == "Unmanaged" and i == 2:
                tbl_item.setForeground(QtGui.QColor("darkred"))
            table.setItem(rows, i, tbl_item)

        table.setSortingEnabled(True)

    def addRowToDB(self, table, list):
        items = ""
        for item in list:
            if item:
                items = items + ", '" + item + "'"
            else:
                items = items + ", ''"

        self.c.execute(
            "INSERT INTO {table} values({values})".format(table=table, values=items[1:])
        )

    def btnBoxActivated(self):
        self.winAddonManager.accept()

    def btnLogClicked(self):
        if self.uiAddonManager.txtLog.isHidden():
            self.uiAddonManager.txtLog.show()
        else:
            self.uiAddonManager.txtLog.hide()

    def addLog(self, message):
        self.uiAddonManager.lblErrors.setText(
            "Errors: " + str(int(self.uiAddonManager.lblErrors.text()[-1]) + 1)
        )
        self.uiAddonManager.txtLog.append(message + "\n")

    def btnAddonsClicked(self):
        if self.uiAddonManager.tabWidget.currentIndex() == 0:
            if self.currentGame.startswith("LOTRO"):
                if self.uiAddonManager.tabWidgetInstalled.currentIndex() == 0:
                    table = self.uiAddonManager.tablePluginsInstalled
                    plugins, details = self.getSelectedAddons(table)

                    num_depends = len(details.split("\n")) - 1
                    if num_depends == 1:
                        plural, plural1 = "this ", " plugin?"
                    else:
                        plural, plural1 = "these ", " plugins?"
                    text = (
                        "Are you sure you want to remove "
                        + plural
                        + str(len(plugins))
                        + plural1
                    )
                    if self.confirmationPrompt(text, details):
                        self.uninstallPlugins(plugins, table)

    def getSelectedAddons(self, table):
        if table.selectedItems():
            selected_addons = []
            details = ""
            for item in table.selectedItems()[0 :: (len(self.COLUMN_LIST) - 4)]:
                # Gets db row id for selected row
                selected_row = int((table.item(item.row(), 0)).text())

                selected_name = table.item(item.row(), 1).text()

                for selected_addon in self.c.execute(
                    "SELECT InterfaceID, File, Name FROM {table} WHERE rowid = ?".format(
                        table=table.objectName()
                    ),
                    (selected_row,),
                ):
                    selected_addons.append(selected_addon)
                    details = details + selected_name + "\n"

            return selected_addons, details

    def uninstallPlugins(self, plugins, table):
        data_folder = os.path.join(self.data_folder, "Plugins")
        for plugin in plugins:
            if plugin[1].endswith(".plugin"):
                plugin_files = [plugin[1]]
            else:
                plugin_files = []
                if self.checkAddonForDependencies(plugin, table):
                    doc = xml.dom.minidom.parse(plugin[1])
                    nodes = doc.getElementsByTagName("Descriptors")[0].childNodes
                    for node in nodes:
                        if node.nodeName == "descriptor":
                            plugin_files.append(
                                os.path.join(
                                    data_folder,
                                    (GetText(node.childNodes).replace("\\", os.sep)),
                                )
                            )
                else:
                    continue

            for plugin_file in plugin_files:
                doc = xml.dom.minidom.parse(plugin_file)
                nodes = doc.getElementsByTagName("Plugin")[0].childNodes
                for node in nodes:
                    if node.nodeName == "Package":
                        plugin_folder = os.path.split(
                            GetText(node.childNodes).replace(".", os.sep)
                        )[0]

                        # Removes plugin and all related files
                        if os.path.exists(data_folder + os.sep + plugin_folder):
                            rmtree(data_folder + os.sep + plugin_folder)
                if os.path.exists(plugin_file):
                    os.remove(plugin_file)
            if os.path.exists(plugin[1]):
                os.remove(plugin[1])

        # Reloads plugins
        self.getInstalledPlugins()

    def checkAddonForDependencies(self, addon, table):
        details = ""

        for dependent in self.c.execute(
            'SELECT Name, Dependencies FROM {table} WHERE Dependencies != ""'.format(
                table=table.objectName()
            )
        ):
            for dependency in dependent[1].split(","):
                if dependency == addon[0]:
                    details = details + dependent[0] + "\n"

        if details:
            num_depends = len(details.split("\n")) - 1
            if num_depends == 1:
                plural = " addon depends"
            else:
                plural = " addons deppend"
            text = (
                str(num_depends)
                + plural
                + " on "
                + addon[2]
                + ". Are you sure you want to remove it?"
            )
            return self.confirmationPrompt(text, details)
        else:
            return True

    def confirmationPrompt(self, text, details):
        messageBox = QtWidgets.QMessageBox(self.parent)
        messageBox.setWindowFlag(QtCore.Qt.FramelessWindowHint)
        messageBox.setIcon(4)
        messageBox.setStandardButtons(messageBox.Apply | messageBox.Cancel)

        messageBox.setInformativeText(text)
        messageBox.setDetailedText(details)

        # Checks if user accepts dialouge
        if messageBox.exec() == 33554432:
            return True
        else:
            return False

    def tabWidgetIndexChanged(self, index):
        if index == 0:
            self.uiAddonManager.btnAddons.setText("-")
            self.uiAddonManager.btnAddons.setToolTip("Remove addons")
        else:
            self.uiAddonManager.btnAddons.setText("+")
            self.uiAddonManager.btnAddons.setToolTip("Install addons")

    def Run(self):
        self.winAddonManager.exec()
        self.closeDB()
