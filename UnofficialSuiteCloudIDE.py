import sublime
import sublime_plugin

import json
import os
import subprocess
import xml.etree.ElementTree as ElementTree

import sublime_lib

weirdErrorPrefix = "[2K[1G"

class projectInfoCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		def everything():
			filePath = self.view.file_name()
			projectPath = findProjectPath(filePath)
			if not projectExists(self, projectPath, filePath):
				return

			fileCabinetFolderPath = getNetSuiteFileCabinetPathFromReadme(projectPath)

			indicator = startIndicator(self, "Getting Project Info")

			# Get Project Name
			projectName = "Not Found"
			try:
				tree = ElementTree.parse(projectPath + os.sep + "src" + os.sep + "manifest.xml")
				root = tree.getroot()
				for child in root:
					if child.tag == "projectname":
						projectName = child.text
						break
			except:
				pass

			# Get Auth ID
			authId = "Not Found"
			try:
				projectJSONFileName = "project.json"
				projectJSONFile = open(projectPath + os.sep + projectJSONFileName, "r")
				projectJSON = json.load(projectJSONFile)
				authId = projectJSON["defaultAuthId"]
			except:
				pass

			# Get Account ID
			# TODO Handle No Auth
			accountId = "Not Found"
			if authId != "Not Found":
				command = "suitecloud account:manageauth --info " + authId
				try:
					authInfo = subprocess.check_output(command, shell=True, universal_newlines=True)
					for line in authInfo.splitlines():
						if line.startswith("Account ID: "):
							accountId = line.replace("Account ID: ", "")
				except subprocess.CalledProcessError as e:
					error = e.output.replace(weirdErrorPrefix, "")
					sublime.error_message(error)

					if "authentication ID (authID) is not available" in error:
						authId += " (Not Found)"

			projectInfo = "Project Name: " + projectName + os.linesep + os.linesep
			projectInfo += "Project Path: " + projectPath + os.linesep + os.linesep
			projectInfo += "File Cabinet Path: " + fileCabinetFolderPath + os.linesep + os.linesep
			projectInfo += "Auth ID: " + authId + os.linesep + os.linesep
			projectInfo += "Account ID: " + accountId + os.linesep

			indicator.stop()

			sublime.message_dialog(projectInfo)

		# Kick off to another thread
		sublime.set_timeout_async(everything, 1)

class compareVersusFileCabinetCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		def everything():
			self.view.run_command('save')
			filePath = self.view.file_name()
			fileName = os.path.split(os.path.abspath(filePath))[1]
			folderPath = os.path.dirname(os.path.abspath(filePath))

			projectPath = findProjectPath(filePath)
			if not projectExists(self, projectPath, filePath):
				return

			os.chdir(projectPath)

			# TODO Get src directory name from suitecloud.config.js
			srcFolder = "src"
			fileCabinetFolderPath = projectPath + os.sep + srcFolder + os.sep + "FileCabinet"

			projectPathDifference = ""
			if folderPath != projectPath:
				projectPathDifference = folderPath.replace(projectPath, "")

			netSuiteFileCabinetPath = getNetSuiteFileCabinetPathFromReadme(projectPath)
			# Normalized to OS path separator
			fileSystemNetSuiteFileCabinetPath = netSuiteFileCabinetPath
			# The README uses forward slashes, fix them if we're on Windows
			if os.sep == "\\":
				fileSystemNetSuiteFileCabinetPath = netSuiteFileCabinetPath.replace("/", "\\")
			if netSuiteFileCabinetPath == False:
				sublime.error_message("README not found.")
				return

			indicator = startIndicator(self, "Downloading " + fileName)

			# Download the file from NetSuite
			importFilePath = netSuiteFileCabinetPath + projectPathDifference.replace("\\", "/") + "/" + fileName
			importResponse = False
			command = "suitecloud file:import --paths \"/" + importFilePath + "\""
			try:
				importResponse = subprocess.check_output(command, shell=True, universal_newlines=True)
			except subprocess.CalledProcessError as e:
				error = e.output.replace(weirdErrorPrefix, "")
				error = error.replace("The imported files will overwrite the project files\n", "")
				# If it's an authentication issue, ask to set up the project auth for the user.
				if "authentication ID (authID) is not available" in e.output or "No account has been set up for this project." in e.output:
					authenticationMessage = error + os.linesep + os.linesep + "Would you like to Setup Project Authentication now?"
					authSetupRequested = sublime.ok_cancel_dialog(authenticationMessage, "Setup Authentication")

					if authSetupRequested:
						setupAuthentication(self, filePath)
						indicator.stop()
						return
				else:
					sublime.error_message(error)

			indicator.stop()

			if importResponse != False and "The following files were imported:" in importResponse:
				# TODO Combine these into a function
				def statusMessage():
					self.view.window().status_message(fileName + " was successfully imported.")
				sublime.set_timeout_async(statusMessage, 1)

				fileCabinetFilePath = fileCabinetFolderPath + os.sep + fileSystemNetSuiteFileCabinetPath + projectPathDifference + os.sep + fileName
				command = "sgdm \"" + filePath + "\" \"" + fileCabinetFilePath + "\""

				try:
					subprocess.check_output(command, shell=True, universal_newlines=True)
				except:
					sublime.error_message("Compare failed. Do you have DiffMerge installed? Make sure you restart Sublime Text after installing DiffMerge.")
					return

				# File imports download XML files along with the requested file.
				# We don't want them clogging stuff up, so we'll delete them.
				lines = importResponse.splitlines()
				filesToDelete = []
				foundFilesStart = False
				for line in lines:
					if foundFilesStart:
						# Convert path to local filesystem path
						if os.sep == "\\":
							line = line.replace("/", "\\")
						path = fileCabinetFolderPath + line

						filesToDelete.append(path)
					else:
						if "The following files were imported:" in line:
							foundFilesStart = True

				# Delete the files to keep the file system clean
				for file in filesToDelete:
					subprocess.call("del \"" + file + "\"", shell=True)

			else:
				if "INVALID FILE PATH:" in importResponse:
					sublime.error_message("File does not exist in the File Cabinet:" + os.linesep + importFilePath)
				else:
					# We don't know what happened. Haven't seen this happen yet.
					sublime.error_message(fileName + " failed to import! Error:" + os.linesep + os.linesep + importResponse.replace(weirdErrorPrefix, ""))

		# Kick off to another thread
		sublime.set_timeout_async(everything, 1)

class manageAuthenticationCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		os.system("suitecloud account:manageauth -i")

class setupAuthenticationCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		filePath = self.view.file_name()
		setupAuthentication(self, filePath)

class createProjectCommand(sublime_plugin.TextCommand):
	def run(self, edit):
		filePath = self.view.file_name()
		createProject(self, filePath)

class uploadFileCommand(sublime_plugin.TextCommand):

	def run(self, edit):
		def everything():
			self.view.run_command('save')
			filePath = self.view.file_name()
			fileName = os.path.split(os.path.abspath(filePath))[1]
			folderPath = os.path.dirname(os.path.abspath(filePath))

			projectPath = findProjectPath(filePath)
			if not projectExists(self, projectPath, filePath):
				return

			os.chdir(projectPath)

			# TODO Get src directory name from suitecloud.config.js
			srcFolder = "src"
			fileCabinetFolderPath = projectPath + os.sep + srcFolder + os.sep + "FileCabinet"

			projectPathDifference = ""
			if folderPath != projectPath:
				projectPathDifference = folderPath.replace(projectPath, "")

			# TODO Add a confirmation of the folder before uploading..
			netSuiteFileCabinetPath = getNetSuiteFileCabinetPathFromReadme(projectPath)
			# Normalized to OS path separator
			fileSystemNetSuiteFileCabinetPath = netSuiteFileCabinetPath
			# The README uses forward slashes, fix them if we're on Windows
			if os.sep == "\\":
				fileSystemNetSuiteFileCabinetPath = netSuiteFileCabinetPath.replace("/", "\\")
			if netSuiteFileCabinetPath == False:
				sublime.error_message("README not found.")
				return

			indicator = startIndicator(self, "Uploading " + fileName)

			# Copy file to the FileCabinet folder of the SDF project
			subprocess.call("xcopy /y \"" + filePath + "\" \"" + fileCabinetFolderPath + os.sep + fileSystemNetSuiteFileCabinetPath + projectPathDifference + os.sep + "\"", shell=True)

			# Upload the file to NetSuite
			success = False
			command = "suitecloud file:upload --paths \"/" + netSuiteFileCabinetPath + projectPathDifference.replace("\\", "/") + "/" + fileName + "\""
			try:
				success = subprocess.check_output(command, shell=True, universal_newlines=True)
			except subprocess.CalledProcessError as e:
				# If it's an authentication issue, ask to set up the project auth for the user.
				if "authentication ID (authID) is not available" in e.output or "No account has been set up for this project." in e.output:
					error = e.output.replace(weirdErrorPrefix, "")
					authenticationMessage = error + os.linesep + os.linesep + "Would you like to Setup Project Authentication now?"
					authSetupRequested = sublime.ok_cancel_dialog(authenticationMessage, "Setup Authentication")

					if authSetupRequested:
						setupAuthentication(self, filePath)
						indicator.stop()
						return
				else:
					sublime.error_message(error)

			indicator.stop()

			if "The following files were uploaded:" in success:
				# TODO Combine these into a function
				print(success)
				def statusMessage():
					self.view.window().status_message(fileName + " was successfully uploaded.")
				sublime.set_timeout_async(statusMessage, 1)
			else:
				# We don't know what happened. Haven't seen this happen yet.
				sublime.error_message(fileName + " failed to upload! Error:" + os.linesep + os.linesep + success.replace(weirdErrorPrefix, ""))

			# Delete the file to keep the file system clean
			subprocess.call("del \"" + fileCabinetFolderPath + os.sep + fileSystemNetSuiteFileCabinetPath + projectPathDifference + os.sep + fileName, shell=True)

		# Kick off to another thread
		sublime.set_timeout_async(everything, 1)

def findProjectPath(filePath):
	projectFileName = "suitecloud.config.js"
	parentPath = getParentPath(filePath)

	# Find Project Directory
	projectPathToCheck = parentPath
	# Do While Hack
	while True:
		found = subprocess.check_output("IF EXIST \"" + projectPathToCheck + os.sep + projectFileName + "\" echo 1", shell=True, universal_newlines=True)
		if (found):
			print("Project Path Found: " + projectPathToCheck)
			return projectPathToCheck
		else:
			if projectPathToCheck == getParentPath(projectPathToCheck):
				return False
			else:
				projectPathToCheck = getParentPath(projectPathToCheck)

def projectExists(self, projectPath, filePath):
	if projectPath == False:
		projectMessage = "Project not found. Would you like to create a new project now?"
		projectRequested = sublime.ok_cancel_dialog(projectMessage, "Create Project")
		if projectRequested:
			createProject(self, filePath)
		return False

	return True

def getParentPath(path):
	return os.path.split(os.path.abspath(path))[0]

def getNetSuiteFileCabinetPathFromReadme(projectPath):
	readmeFileName = "README.txt"

	# Find Project Directory
	readmePath = projectPath
	# Do While Hack
	while True:
		found = subprocess.check_output("IF EXIST \"" + readmePath + os.sep + readmeFileName + "\" echo 1", shell=True, universal_newlines=True)
		if (found):
			print("README Path Found: " + readmePath)
			break
		else:
			if readmePath == getParentPath(readmePath):
				return False
			else:
				readmePath = getParentPath(readmePath)

	readmeFile = open(readmePath + os.sep + readmeFileName, "r")
	readmeFileLines = readmeFile.readlines()

	for line in readmeFileLines:
		if line.startswith("SuiteScripts/") or line.startswith("SuiteBundles/"):
			print("Found NetSuite File Cabinet Path: " + line.strip())
			return line.strip()

	return False

def setupAuthentication(self, filePath):
	projectPath = findProjectPath(filePath)
	if not projectExists(self, projectPath, filePath):
		return

	os.chdir(projectPath)

	os.system("suitecloud account:setup")

def createProject(self, filePath):
	folderPath = os.path.dirname(os.path.abspath(filePath))

	# Prompt the user for the Project Path then prompt the user for the Project Name.
	def projectPathChosen(path):
		def projectNameChosen(projectName):
			# TODO Add indicator?
			print("Creating Project: " + projectName + " . . .")

			# Have to go to the parent directory because SuiteCloud CLI
			# creates the folder for the project in the currend directory
			os.chdir(getParentPath(path))

			# Check Java's version first. I've seen the project folder be deleted when running this without JDK 11 being installed.
			returned = ""
			try:
				returned = subprocess.check_output("java --version", shell=True, universal_newlines=True)
				if not returned.startswith("java 11"):
					sublime.error_message("Java 11 Not Found." + os.linesep + os.linesep + returned)
					return
			except subprocess.CalledProcessError as e:
				sublime.error_message("Java 11 Not Found." + os.linesep + os.linesep + returned)
				return

			# TODO Handle Errors
			try:
				returned = subprocess.check_output("suitecloud project:create --type ACCOUNTCUSTOMIZATION --projectname \"" + projectName +"\"", shell=True, universal_newlines=True)
			except subprocess.CalledProcessError as e:
				sublime.error_message(e.output.replace(weirdErrorPrefix, ""))
				return

			print(projectName + " was successfully created.")
			def statusMessage():
				self.view.window().status_message(projectName + " was successfully created.")
			sublime.set_timeout_async(statusMessage, 1)

		# Chop off the last separator if there is one
		if path.endswith(os.sep):
			print(path[:-1])
			path = path[:-1]

		self.view.window().show_input_panel("Project Name", os.path.basename(path), projectNameChosen, None, None)

	self.view.window().show_input_panel("Project Path (Same as the project's path in Eclipse)", folderPath, projectPathChosen, None, None)

def startIndicator(self, text):
	print(text + " . . .")
	indicator = sublime_lib.ActivityIndicator(self.view.window(), text)
	indicator.start()
	return indicator
