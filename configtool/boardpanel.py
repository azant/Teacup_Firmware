
import os
import wx
import re

from configtool.data import (defineValueFormat,
                             defineBoolFormat, defineHeaterFormat, reCommDefBL,
                             reCommDefBoolBL, reHelpTextStart, reHelpTextEnd,
                             reStartSensors, reEndSensors, reStartHeaters,
                             reEndHeaters, reCandHeatPins, reCandThermPins,
                             reCandProcessors, reCandCPUClocks, reFloatAttr,
                             reDefine, reDefineBL, reDefQS, reDefQSm,
                             reDefQSm2, reDefBool, reDefBoolBL, reDefHT,
                             reDefTS, reDefTT, reSensor, reHeater, reTempTable)
from configtool.pinoutspage import PinoutsPage
from configtool.sensorpage import SensorsPage
from configtool.heaterspage import HeatersPage
from configtool.communicationspage import CommunicationsPage
from configtool.cpupage import CpuPage
from configtool.protectedfiles import protectedFiles
from configtool.thermistortablefile import generateTempTables


class BoardPanel(wx.Panel):
  def __init__(self, parent, nb, settings):
    wx.Panel.__init__(self, nb, wx.ID_ANY)
    self.parent = parent
    self.settings = settings
    self.protFileLoaded = False

    self.configFile = None

    self.cfgValues = {}
    self.heaters = []
    self.sensors = []
    self.candHeatPins = []
    self.candThermPins = []
    self.dir = os.path.join(self.settings.folder, "config")

    sz = wx.BoxSizer(wx.HORIZONTAL)

    self.nb = wx.Notebook(self, wx.ID_ANY, size = (21, 21),
                          style = wx.BK_DEFAULT)
    self.nb.SetFont(self.settings.font)

    self.pages = []
    self.titles = []
    self.pageModified = []
    self.pageValid = []

    self.pgCpu = CpuPage(self, self.nb, len(self.pages), self.settings.font)
    text = "CPU"
    self.nb.AddPage(self.pgCpu, text)
    self.pages.append(self.pgCpu)
    self.titles.append(text)
    self.pageModified.append(False)
    self.pageValid.append(True)

    self.pgPins = PinoutsPage(self, self.nb, len(self.pages),
                              self.settings.font)
    text = "Pinouts"
    self.nb.AddPage(self.pgPins, text)
    self.pages.append(self.pgPins)
    self.titles.append(text)
    self.pageModified.append(False)
    self.pageValid.append(True)

    self.pgSensors = SensorsPage(self, self.nb, len(self.pages),
                                 self.settings.font)
    text = "Temperature Sensors"
    self.nb.AddPage(self.pgSensors, text)
    self.pages.append(self.pgSensors)
    self.titles.append(text)
    self.pageModified.append(False)
    self.pageValid.append(True)

    self.pgHeaters = HeatersPage(self, self.nb, len(self.pages),
                                 self.settings.font)
    text = "Heaters"
    self.nb.AddPage(self.pgHeaters, text)
    self.pages.append(self.pgHeaters)
    self.titles.append(text)
    self.pageModified.append(False)
    self.pageValid.append(True)

    self.pgCommunications = CommunicationsPage(self, self.nb, len(self.pages),
                                               self.settings.font)
    text = "Communications"
    self.nb.AddPage(self.pgCommunications, text)
    self.pages.append(self.pgCommunications)
    self.titles.append(text)
    self.pageModified.append(False)
    self.pageValid.append(True)

    sz.Add(self.nb, 1, wx.EXPAND + wx.ALL, 5)

    self.SetSizer(sz)
    self.Fit()

  def getCPUInfo(self):
    vF_CPU = None
    if 'F_CPU' in self.cfgValues.keys():
      vF_CPU = self.cfgValues['F_CPU']

    vCPU = None
    if 'CPU' in self.cfgValues.keys():
      vCPU = self.cfgValues['CPU']

    return vF_CPU, vCPU

  def assertModified(self, pg, flag = True):
    self.pageModified[pg] = flag
    self.modifyTab(pg)

  def isModified(self):
    return (True in self.pageModified)

  def isValid(self):
    return not (False in self.pageValid)

  def hasData(self):
    return (self.configFile != None)

  def getFileName(self):
    return self.configFile

  def assertValid(self, pg, flag = True):
    self.pageValid[pg] = flag
    self.modifyTab(pg)

    if False in self.pageValid:
      self.parent.enableSaveBoard(False, False)
    else:
      self.parent.enableSaveBoard(not self.protFileLoaded, True)

  def modifyTab(self, pg):
    if self.pageModified[pg] and not self.pageValid[pg]:
      pfx = "?* "
    elif self.pageModified[pg]:
      pfx = "* "
    elif not self.pageValid[pg]:
      pfx = "? "
    else:
      pfx = ""

    self.nb.SetPageText(pg, pfx + self.titles[pg])
    if True in self.pageModified and False in self.pageValid:
      pfx = "?* "
    elif True in self.pageModified:
      pfx = "* "
    elif False in self.pageValid:
      pfx = "? "
    else:
      pfx = ""
    self.parent.setBoardTabDecor(pfx)

  def setHeaters(self, ht):
    self.parent.setHeaters(ht)

  def onClose(self, evt):
    if not self.confirmLoseChanges("exit"):
      return

    self.Destroy()

  def confirmLoseChanges(self, msg):
    if True not in self.pageModified:
      return True

    dlg = wx.MessageDialog(self, "Are you sure you want to " + msg + "?\n"
                                 "There are changes to your board "
                                 "configuration that will be lost.",
                           "Changes pending",
                           wx.YES_NO | wx.NO_DEFAULT | wx.ICON_INFORMATION)
    rc = dlg.ShowModal()
    dlg.Destroy()

    if rc != wx.ID_YES:
      return False

    return True

  def onLoadConfig(self, evt):
    if not self.confirmLoseChanges("load a new board configuration"):
      return

    wildcard = "Board configuration (board.*.h)|board.*.h"

    dlg = wx.FileDialog(self, message = "Choose a board config file",
                        defaultDir = self.dir, defaultFile = "",
                        wildcard = wildcard, style = wx.OPEN | wx.CHANGE_DIR)

    path = None
    if dlg.ShowModal() == wx.ID_OK:
      path = dlg.GetPath()

    dlg.Destroy()
    if path is None:
      return


    self.dir = os.path.dirname(path)
    rc = self.loadConfigFile(path)

    if not rc:
      dlg = wx.MessageDialog(self, "Unable to process file %s." % path,
                             "File error", wx.OK + wx.ICON_ERROR)
      dlg.ShowModal()
      dlg.Destroy()
      return

  def loadConfigFile(self, fn):
    try:
      self.cfgBuffer = list(open(fn))
    except:
      return False

    self.configFile = fn

    self.processors = []
    self.sensors = []
    self.heaters = []
    self.candHeatPins = []
    self.candThermPins = []
    self.candProcessors = []
    self.candClocks = []
    tempTables = {}
    gatheringHelpText = False
    helpTextString = ""
    helpKey = None

    self.cfgValues = {}
    self.helpText = {}

    prevLines = ""
    for ln in self.cfgBuffer:
      if gatheringHelpText:
        if reHelpTextEnd.match(ln):
          gatheringHelpText = False
          hk = helpKey.split()
          for k in hk:
            self.helpText[k] = helpTextString
          helpTextString = ""
          helpKey = None
          continue
        else:
          helpTextString += ln
          continue

      m = reHelpTextStart.match(ln)
      if m:
        t = m.groups()
        gatheringHelpText = True
        helpKey = t[0]
        continue

      if ln.rstrip().endswith("\\"):
        prevLines += ln.rstrip()[:-1]
        continue

      if prevLines != "":
        ln = prevLines + ln
        prevLines = ""

      if ln.lstrip().startswith("//"):
        m = reCandThermPins.match(ln)
        if m:
          t = m.groups()
          if len(t) == 1:
            self.candThermPins.append(t[0])
            continue

        m = reCandHeatPins.match(ln)
        if m:
          t = m.groups()
          if len(t) == 1:
            self.candHeatPins.append(t[0])
            continue

        m = reCandProcessors.match(ln)
        if m:
          t = m.groups()
          if len(t) == 1:
            self.candProcessors.append(t[0])
            continue

        m = reCandCPUClocks.match(ln)
        if m:
          t = m.groups()
          if len(t) == 1:
            self.candClocks.append(t[0])
            continue

        m = reDefTT.match(ln)
        if m:
          t = m.groups()
          if len(t) == 2:
            s = self.parseTempTable(t[1])
            if s:
              tempTables[t[0]] = s
            continue

        continue

      if ln.lstrip().startswith("#define"):
        m = reDefQS.search(ln)
        if m:
          t = m.groups()
          if len(t) == 2:
            m = reDefQSm.search(ln)
            if m:
              t = m.groups()
              tt = re.findall(reDefQSm2, t[1])
              if len(tt) == 1:
                self.cfgValues[t[0]] = tt[0]
                continue
              elif len(tt) > 1:
                self.cfgValues[t[0]] = tt
                continue

        m = reDefine.search(ln)
        if m:
          t = m.groups()
          if len(t) == 2:
            self.cfgValues[t[0]] = t[1]
            if reFloatAttr.search(ln):
              pass
            continue

        m = reDefBool.search(ln)
        if m:
          t = m.groups()
          if len(t) == 1:
            self.cfgValues[t[0]] = True

      else:
        m = reDefTS.search(ln)
        if m:
          t = m.groups()
          if len(t) == 1:
            s = self.parseSensor(t[0])
            if s:
              self.sensors.append(s)
            continue

        m = reDefHT.search(ln)
        if m:
          t = m.groups()
          if len(t) == 1:
            s = self.parseHeater(t[0])
            if s:
              self.heaters.append(s)
            continue

    for k in range(len(self.sensors)):
      tn = self.sensors[k][0].upper()
      if tn in tempTables.keys():
        self.sensors[k][3] = tempTables[tn]

    if os.path.basename(fn) in protectedFiles:
      self.parent.enableSaveBoard(False, True)
      self.protFileLoaded = True
    else:
      self.protFileLoaded = False
      self.parent.enableSaveBoard(True, True)
    self.parent.setBoardTabFile(os.path.basename(fn))
    self.pgHeaters.setCandidatePins(self.candHeatPins)
    self.pgSensors.setCandidatePins(self.candThermPins)
    self.pgCpu.setCandidateProcessors(self.candProcessors)
    self.pgCpu.setCandidateClocks(self.candClocks)

    for pg in self.pages:
      pg.insertValues(self.cfgValues)
      pg.setHelpText(self.helpText)

    self.pgSensors.setSensors(self.sensors)
    self.pgHeaters.setHeaters(self.heaters)

    return True

  def parseSensor(self, s):
    m = reSensor.search(s)
    if m:
      t = m.groups()
      if len(t) == 4:
        return list(t)
    return None

  def parseHeater(self, s):
    m = reHeater.search(s)
    if m:
      t = m.groups()
      if len(t) == 3:
        return list(t)
    return None

  def parseTempTable(self, s):
    m = reTempTable.search(s)
    if m:
      t = m.groups()
      if len(t) == 4:
        return list(t)
    return None

  def onSaveConfig(self, evt):
    path = self.configFile
    return self.saveConfigFile(path)

  def onSaveConfigAs(self, evt):
    wildcard = "Board configuration (board.*.h)|board.*.h"

    dlg = wx.FileDialog(self, message = "Save as ...", defaultDir = self.dir,
                        defaultFile = "", wildcard = wildcard,
                        style = wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)

    val = dlg.ShowModal()

    if val != wx.ID_OK:
      dlg.Destroy()
      return

    path = dlg.GetPath()
    dlg.Destroy()

    rc = self.saveConfigFile(path)
    if rc:
      self.parent.setBoardTabFile(os.path.basename(path))
      self.protFileLoaded = False
      self.parent.enableSaveBoard(True, True)
    return rc

  def saveConfigFile(self, path):
    if os.path.basename(path) in protectedFiles:
      dlg = wx.MessageDialog(self, "Unable to overwrite %s." % path,
                             "Protected file error", wx.OK + wx.ICON_ERROR)
      dlg.ShowModal()
      dlg.Destroy()
      return False

    if not os.path.basename(path).startswith("board."):
      dlg = wx.MessageDialog(self, "Illegal file name: %s.\n"
                                   "File name must begin with \"board.\"" % path,
                             "Illegal file name", wx.OK + wx.ICON_ERROR)
      dlg.ShowModal()
      dlg.Destroy()
      return False

    ext = os.path.splitext(os.path.basename(path))[1]
    self.dir = os.path.dirname(path)

    if ext == "":
      path += ".h"

    try:
      fp = file(path, 'w')
    except:
      dlg = wx.MessageDialog(self, "Unable to write to file %s." % path,
                             "File error", wx.OK + wx.ICON_ERROR)
      dlg.ShowModal()
      dlg.Destroy()
      return False

    self.configFile = path

    values = {}
    labelFound = []

    for pg in self.pages:
      v1 = pg.getValues()
      for k in v1.keys():
        values[k] = v1[k]

    skipToSensorEnd = False
    skipToHeaterEnd = False
    tempTables = {}
    for ln in self.cfgBuffer:
      m = reStartSensors.match(ln)
      if m:
        fp.write(ln)
        fp.write("//                 name      type           pin    "
                 "additional\n");
        ttString = "\n//                     r0      beta  r2    vadc\n"
        for s in self.sensors:
          sstr = "%-10s%-15s%-7s" % ((s[0] + ","), (s[1] + ","), (s[2] + ","))
          if s[3] != "NONE":
            tt = s[3]
            sstr += "THERMISTOR_%s" % s[0].upper()
            ttString += "//TEMP_TABLE %-8s (%-8s%-6s%-6s%s)\n" % \
                        (s[0].upper(), (tt[0] + ","), (tt[1] + ","),
                         (tt[2] + ","), tt[3])
          else:
            sstr += s[3]
          fp.write("DEFINE_TEMP_SENSOR(%s)\n" % sstr)
        fp.write(ttString)
        skipToSensorEnd = True
        continue

      if skipToSensorEnd:
        m = reEndSensors.match(ln)
        if m:
          fp.write(ln)
          skipToSensorEnd = False
        continue

      m = reStartHeaters.match(ln)
      if m:
        fp.write(ln)
        fp.write("//            name      port   pwm\n")
        for s in self.heaters:
          sstr = "%-10s%-7s%s" % ((s[0] + ","), (s[1] + ","), s[2])
          fp.write("DEFINE_HEATER(%s)\n" % sstr)
        fp.write("\n")
        for s in self.heaters:
          fp.write(defineHeaterFormat % (s[0].upper(), s[0]))
        skipToHeaterEnd = True
        continue

      if skipToHeaterEnd:
        m = reEndHeaters.match(ln)
        if m:
          fp.write(ln)
          skipToHeaterEnd = False
        continue

      m = reDefineBL.match(ln)
      if m:
        t = m.groups()
        if len(t) == 2:
          if t[0] in values.keys() and values[t[0]] != "":
            fp.write(defineValueFormat % (t[0], values[t[0]]))
            self.cfgValues[t[0]] = values[t[0]]
            labelFound.append(t[0])
          elif t[0] in values.keys():
            fp.write("//" + ln)
            if t[0] in self.cfgValues.keys():
              del self.cfgValues[t[0]]
            labelFound.append(t[0])
          else:
            fp.write(ln)
          continue

      m = reDefBoolBL.match(ln)
      if m:
        t = m.groups()
        if len(t) == 1:
          if t[0] in values.keys() and values[t[0]]:
            fp.write(defineBoolFormat % t[0])
            self.cfgValues[t[0]] = True
            labelFound.append(t[0])
          elif t[0] in values.keys():
            fp.write("//" + ln)
            if t[0] in self.cfgValues.keys():
              del self.cfgValues[t[0]]
            labelFound.append(t[0])
          else:
            fp.write(ln)
          continue

      m = reCommDefBL.match(ln)
      if m:
        t = m.groups()
        if len(t) == 2:
          if t[0] in values.keys() and values[t[0]] != "":
            fp.write(defineValueFormat % (t[0], values[t[0]]))
            self.cfgValues[t[0]]  = values[t[0]]
            labelFound.append(t[0])
          elif t[0] in values.keys():
            fp.write(ln)
            labelFound.append(t[0])
          else:
            fp.write(ln)
          continue

      m = reCommDefBoolBL.match(ln)
      if m:
        t = m.groups()
        if len(t) == 1:
          if t[0] in values.keys() and values[t[0]]:
            fp.write(defineBoolFormat % t[0])
            self.cfgValues[t[0]] = True
            labelFound.append(t[0])
          elif t[0] in values.keys():
            fp.write(ln)
            labelFound.append(t[0])
          else:
            fp.write(ln)
          continue

      fp.write(ln)

    for k in labelFound:
      del values[k]

    newLabels = ""
    for k in values.keys():
      if newLabels == "":
        newLabels = k
      else:
        newLabels += ", " + k
      self.addNewDefine(fp, k, values[k])

    if newLabels != "":
      dlg = wx.MessageDialog(self, "New defines added to board config:\n" +
                             newLabels, "New defines",
                             wx.OK + wx.ICON_INFORMATION)
      dlg.ShowModal()
      dlg.Destroy()

    fp.close()

    if not generateTempTables(self.sensors, self.settings):
      dlg = wx.MessageDialog(self, "Error writing to file thermistortable.h.",
                             "File error", wx.OK + wx.ICON_ERROR)
      dlg.ShowModal()
      dlg.Destroy()
      return False

    return True

  def addNewDefine(self, fp, key, val):
    fp.write("\n")
    fp.write("/** \\def %s\n" % key)
    fp.write("  Add help text here.\n")
    fp.write("*/\n")
    if val == True:
      fp.write(defineBoolFormat % key)
    elif val == False:
      fp.write("//#define %s\n" % key)
    elif val == "":
      fp.write("//#define %s\n" % key)
    else:
      fp.write(defineValueFormat % (key, val))
