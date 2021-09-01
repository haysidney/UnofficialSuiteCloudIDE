import sublime
import sublime_plugin

import os
import subprocess

import sublime_lib

class uploadFileCommand(sublime_plugin.TextCommand):

	def run(self, edit):
		def everything():
			self.view.run_command('save');
			filePath = self.view.file_name();
			fileName = os.path.split(os.path.abspath(filePath))[1];
			folderPath = os.path.dirname(os.path.abspath(filePath));

			projectPath = findProjectPath(filePath);
			if projectPath == False:
				sublime.message_dialog("Project not found.");
				return;

			os.chdir(projectPath);

			# TODO Get src directory name from suitecloud.config.js
			srcFolder = "src";
			fileCabinetFolderPath = projectPath + os.sep + srcFolder + os.sep + "FileCabinet";

			projectPathDifference = "";
			if folderPath != projectPath:
				projectPathDifference = folderPath.replace(projectPath, "")

			# TODO Add a confirmation of the folder before uploading..
			netSuiteFileCabinetPath = getNetSuiteFileCabinetPathFromReadme(projectPath);
			# Normalized to OS path separator
			fileSystemNetSuiteFileCabinetPath = netSuiteFileCabinetPath;
			# The README uses forward slashes, fix them if we're on Windows
			if os.sep == "\\":
				fileSystemNetSuiteFileCabinetPath = netSuiteFileCabinetPath.replace("/", "\\");
			if netSuiteFileCabinetPath == False:
				sublime.message_dialog("README not found.");
				return;

			# TODO Combine these into a function
			print("Uploading " + fileName + " . . .");
			indicator = sublime_lib.ActivityIndicator(self.view.window(), "Uploading " + fileName)
			indicator.start();

			# Copy file to the FileCabinet folder of the SDF project
			subprocess.call("xcopy \"" + filePath + "\" \"" + fileCabinetFolderPath + os.sep + fileSystemNetSuiteFileCabinetPath + projectPathDifference + os.sep + "\"", shell=True);

			# Upload the file to NetSuite
			command = "suitecloud file:upload --paths \"/" + netSuiteFileCabinetPath + projectPathDifference.replace("\\", "/") + "/" + fileName + "\"";
			success = subprocess.check_output(command, shell=True, universal_newlines=True);

			indicator.stop();

			if "The following files were uploaded:" in success:
				# TODO Combine these into a function
				print(fileName + " was successfully uploaded.");
				def statusMessage():
					self.view.window().status_message(fileName + " was successfully uploaded.");
				sublime.set_timeout_async(statusMessage, 1);
			else:
				print(fileName + " failed to upload! Error:" + os.linesep + success);
				sublime.message_dialog(fileName + " failed to upload! Error:" + os.linesep + os.linesep + success);

			# Delete the file to keep the file system clean
			subprocess.call("del \"" + fileCabinetFolderPath + os.sep + fileSystemNetSuiteFileCabinetPath + projectPathDifference + os.sep + fileName, shell=True);

		sublime.set_timeout_async(everything, 1);

def findProjectPath(filePath):
	projectFileName = "suitecloud.config.js";
	parentPath = getParentPath(filePath);

	# Find Project Directory
	projectPathToCheck = parentPath;
	# Do While Hack
	while True:
		print(projectPathToCheck);
		found = subprocess.check_output("IF EXIST \"" + projectPathToCheck + os.sep + projectFileName + "\" echo 1", shell=True, universal_newlines=True);
		if (found):
			print("Project Path Found: " + projectPathToCheck);
			return projectPathToCheck;
		else:
			if projectPathToCheck == getParentPath(projectPathToCheck):
				return False;
			else:
				projectPathToCheck = getParentPath(projectPathToCheck);

def getParentPath(path):
	return os.path.split(os.path.abspath(path))[0];

def getNetSuiteFileCabinetPathFromReadme(projectPath):
	readmeFileName = "README.txt";

	# Find Project Directory
	readmePath = projectPath;
	# Do While Hack
	while True:
		print(readmePath);
		found = subprocess.check_output("IF EXIST \"" + readmePath + os.sep + readmeFileName + "\" echo 1", shell=True, universal_newlines=True);
		if (found):
			print("README Path Found: " + readmePath);
			break;
		else:
			if readmePath == getParentPath(readmePath):
				return False;
			else:
				readmePath = getParentPath(readmePath);

	readmeFile = open(readmePath + os.sep + readmeFileName, "r");
	readmeFileLines = readmeFile.readlines();

	for line in readmeFileLines:
		if (line.startswith("SuiteScripts/")):
			print("Found NetSuite File Cabinet Path: " + line.strip());
			return line.strip();

	return False;