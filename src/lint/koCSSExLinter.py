#!python
# Copyright (c) 2000-2011 ActiveState Software Inc.
# See the file LICENSE.txt for licensing information.

# Use the silvercity tokenizer and parse text here
# Support for SCSS (CSS-like Sass) and Less as well.

import os.path
import process
import re
import tempfile
import which

from koLintResult import createAddResult, KoLintResult
import koLintResult
from koLintResults import koLintResults
import koprocessutils
import logging
from xpcom import components

from KoCSSLinter import koCSSLinter

log = logging.getLogger("koCSSLinter")
#log.setLevel(logging.DEBUG)
    
class KoSCSSCommonLinter(KoCSSLinter):
    """Handle both scss and sass here. They both use ruby, and are essentially
    using the same processor.
    """
    _scss_emsg_ptn = re.compile(r'^\s*on line (\d+) of (.*)$')
    _syntaxErrorPtn = re.compile(r'^(?:Syntax )?[eE]rror:\s*(.*)$')
    _sass_wmsg_pth = re.compile(r'^WARNING on line (\d+) of (.*)$')
    def lint_with_text(self, request, text):
        try:
            prefset = request.prefset
            linterPrefName = "%sLinterType" % self.cmd
            scssLinterType = prefset.getStringPref(linterPrefName)
            if scssLinterType == "none":
                return
            if scssLinterType == "builtin":
                return KoCSSLinter().lint_with_text(request, text)
            interpreterPrefName = "%sDefaultInterpreter" % self.cmd
            scssPath = prefset.getStringPref(interpreterPrefName)
            # The 'or' part handles any language for "Find on Path"
            if (not scssPath) or not os.path.exists(scssPath):
                try:
                    scssPath = which.which(self.cmd)
                except which.WhichError:
                    pass
            if not scssPath or not os.path.exists(scssPath):
                log.warn("Setting %sLinterType to 'default': %s not found", self.cmd, self.cmd)
                prefset.setStringPref(linterPrefName, "builtin")
                return KoCSSLinter().lint_with_text(request, text)
            else:
                prefset.setStringPref(interpreterPrefName, scssPath)
            rubyPath = prefset.getStringPref("rubyDefaultInterpreter")
            if (not rubyPath) or not os.path.exists(rubyPath):
                try:
                    rubyPath = which.which("ruby")
                except which.WhichError:
                    pass
                if (not rubyPath) or not os.path.exists(rubyPath):
                    log.warn("Setting %s to 'default': no ruby found to drive %s", linterPrefName, self.cmd)
                    prefset.setStringPref(linterPrefName, "builtin")
                    return KoCSSLinter.lint_with_text(self, request, text)
                else:
                    prefset.setStringPref("rubyDefaultInterpreter", rubyPath)
            
            # Run scss
            tmpfilename = tempfile.mktemp() + '.' + self.cmd
            fout = open(tmpfilename, 'wb')
            fout.write(text)
            fout.close()
            textlines = text.splitlines()
            try:
                which.which("rbenv")
                cmd = [scssPath, "-I", request.cwd or '.', "-c", tmpfilename]
            except which.WhichError:
                cmd = [rubyPath, scssPath, "-I", request.cwd or '.', "-c", tmpfilename]
            #koLintResult.insertNiceness(cmd)
            cwd = request.cwd or None
            # We only need the stderr result.
            try:
                p = process.ProcessOpen(cmd, cwd=cwd, env=koprocessutils.getUserEnv(), stdin=None)
                stderr = p.communicate()[1]
                warnLines = stderr.splitlines(0) # Don't need the newlines.
            except:
                warnLines = []
            finally:
                os.unlink(tmpfilename)
        except:
            log.exception("scss: lint_with_text: big fail")
            warnLines = []
        results = koLintResults()
        prevLine = ""
        for i, line in enumerate(warnLines):
            m = self._scss_emsg_ptn.match(line)
            w = self._sass_wmsg_pth.match(line)
            if w:
                lineNo = int(w.group(1))
                severity = koLintResult.SEV_WARNING
                msg = warnLines[i + 1]
                desc = self.cmd + ": " + msg
                koLintResult.createAddResult(results, textlines, severity, lineNo, desc)
            if m:
                lineNo = int(m.group(1))
                m2 = self._syntaxErrorPtn.match(prevLine)
                if m2:
                    severity = koLintResult.SEV_ERROR
                    msg = m2.group(1)
                else:
                    severity = koLintResult.SEV_WARNING
                    msg = prevLine
                desc = self.cmd + ": " + msg
                koLintResult.createAddResult(results, textlines, severity, lineNo, desc)
            else:
                prevLine = line
        return results
    
class KoSCSSLinter(KoSCSSCommonLinter):
    _com_interfaces_ = [components.interfaces.koILinter,
                        components.interfaces.nsIConsoleListener]
    _reg_desc_ = "Komodo SCSS Linter"
    _reg_clsid_ = "{32b99faa-e3aa-49dc-a54f-4a7a245ff199}"
    _reg_contractid_ = "@activestate.com/koLinter?language=SCSS;1"
    _reg_categories_ = [
         ("category-komodo-linter", 'SCSS'),
         ]
    cmd = "scss"
        
class KoSassLinter(KoSCSSCommonLinter):
    _com_interfaces_ = [components.interfaces.koILinter,
                        components.interfaces.nsIConsoleListener]
    _reg_desc_ = "Komodo Sass Linter"
    _reg_clsid_ = "{03fa17fc-fab6-4573-93c5-ed82793a04a6}"
    _reg_contractid_ = "@activestate.com/koLinter?language=Sass;1"
    _reg_categories_ = [
         ("category-komodo-linter", 'Sass'),
         ]
    cmd = "sass"

class KoLessLinter(KoCSSLinter):
    _com_interfaces_ = [components.interfaces.koILinter,
                        components.interfaces.nsIConsoleListener]
    _reg_desc_ = "Komodo Less Linter"
    _reg_clsid_ = "{e499324f-e35b-48ec-86fe-618c7f54f013}"
    
    _reg_contractid_ = "@activestate.com/koLinter?language=Less;1"
    _reg_categories_ = [
         ("category-komodo-linter", 'Less'),
         ]
            
    _less_emsg_ptn = re.compile(r'^.*?Error:\s*(.*?)\s+in\s+.*?\s+on\s+line\s+(\d+),\s+column\s+(\d+)')
    _less_emsg_ptn_old = re.compile(r'^.*?Error:\s*(.*?)\s+on\s+line\s+(\d+)\s+in\s') # older versions
    def lint_with_text(self, request, text):
        try:
            prefset = request.prefset
            lessLinterType = prefset.getStringPref("lessLinterType")
            if lessLinterType == "none":
                return
            if lessLinterType == "builtin":
                return KoCSSLinter.lint_with_text(self, request, text)
            lessPath = prefset.getStringPref("lessDefaultInterpreter")
            # The 'or' part handles any language for "Find on Path"
            if (not lessPath) or not os.path.exists(lessPath):
                try:
                    lessPath = which.which("lessc")
                except which.WhichError:
                    pass
                if (not lessPath) or not os.path.exists(lessPath):
                    log.warn("Setting lessLinterType to 'default': less not found")
                    prefset.setStringPref("lessLinterType", "builtin")
                    return KoCSSLinter.lint_with_text(self, request, text)
                else:
                    prefset.setStringPref("lessDefaultInterpreter", lessPath)
            nodePath = prefset.getStringPref("nodejsDefaultInterpreter")
            if (not nodePath) or not os.path.exists(nodePath):
                try:
                    nodePath = which.which("node")
                except which.WhichError:
                    pass
                if (not nodePath) or not os.path.exists(nodePath):
                    log.warn("Setting lessLinterType to 'default': no node found to drive less")
                    prefset.setStringPref("lessLinterType", "builtin")
                    return KoCSSLinter.lint_with_text(self, request, text)
                else:
                    prefset.setStringPref("nodejsDefaultInterpreter", nodePath)
            
            # Run less
            tmpfilename = tempfile.mktemp() + '.less'
            fout = open(tmpfilename, 'wb')
            fout.write(text)
            fout.close()
            textlines = text.splitlines()
            cmd = [nodePath, lessPath, "--no-color", tmpfilename]
            #koLintResult.insertNiceness(cmd)
            cwd = request.cwd or None
            # We only need the stderr result.
            try:
                p = process.ProcessOpen(cmd, cwd=cwd, env=koprocessutils.getUserEnv(), stdin=None)
                stderr = p.communicate()[1]
                warnLines = stderr.splitlines(0) # Don't need the newlines.
            except:
                warnLines = []
            finally:
                os.unlink(tmpfilename)
        except:
            log.exception("less: lint_with_text: big fail")
            warnLines = []
        
        # They're all errors for this checker
        # (and they all say "Syntax Checker!")
        # (at least version 1.3.0 of the LESS Compiler does).
        severity = koLintResult.SEV_ERROR
        results = koLintResults()
        for line in warnLines:
            m = self._less_emsg_ptn.match(line)
            if m:
                lineNo = int(m.group(2))
                desc = m.group(1)
                column = int(m.group(3))
                koLintResult.createAddResult(results, textlines, severity, lineNo, desc, columnStart=column)
            else:
                m = self._less_emsg_ptn_old.match(line)
                if m:
                    lineNo = int(m.group(2))
                    desc = m.group(1)
                    koLintResult.createAddResult(results, textlines, severity, lineNo, desc)
        return results

