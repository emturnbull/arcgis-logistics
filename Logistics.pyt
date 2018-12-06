import arcpy
import time
import os

class Toolbox(object):
	def __init__(self):
		self.label = "Spatial Logistics"
		self.alias = ""
		self.tools = [PolylineCost, ShortestPath, AllocateProduction]


class PolylineCost(object):
	def __init__(self):
		"""Define the tool (tool name is the name of the class)."""
		self.label = "Calculate Polyline Cost"
		self.description = "Determine the cost of a polyline running through a cost surface raster. Cost is equal to the distance-weighted sum of the underlying cells."
		self.canRunInBackground = False
		self.category = "Utility Tools"

	def getParameterInfo(self):
		"""Define parameter definitions"""
		params = []
		params.append(arcpy.Parameter(
				displayName = "Input Features",
				name = "in_features",
				datatype = "GPFeatureLayer",
				parameterType = "Required",
				direction = "Input"
			)
		)
		params[0].filter.list = ["Polyline"]
		params.append(arcpy.Parameter(
			displayName = "Feature Cost Field",
			name = "cost_field",
			datatype = "Field",
			parameterType = "Required",
			direction = "Input"
		))
		params[1].parameterDependencies = [params[0].name]
		params[1].list = ["Double", "Float", "Single", "Short", "Long"]
		params.append(arcpy.Parameter(
			displayName = "Cost Surface",
			name = "cost_surface",
			datatype = "Raster Layer",
			parameterType = "Required",
			direction = "Input"
		))
		params.append(arcpy.Parameter(
				displayName = "Modified Features",
				name = "out_features",
				datatype = "GPFeatureLayer",
				parameterType = "Derived",
				direction = "Output"
		))

		return params

	def isLicensed(self):
		"""Set whether tool is licensed to execute."""
		return True

	def updateParameters(self, parameters):
		"""Modify the values and properties of parameters before internal
		validation is performed.  This method is called whenever a parameter
		has been changed."""
		return

	def updateMessages(self, parameters):
		"""Modify the messages created by internal validation for each tool
		parameter.  This method is called after internal validation."""
		return
		
	def rasterCellExtent(self, costRaster, currentFeature): 
		extent = [
			math.floor(max(0, currentFeature.extent.XMin - costRaster.extent.XMin) / costRaster.meanCellWidth),	# Left-most cell number
			costRaster.width - math.floor(max(0, costRaster.extent.XMax - currentFeature.extent.XMax) / costRaster.meanCellWidth), # Right-most cell number 
			math.floor(max(0, currentFeature.extent.YMin - costRaster.extent.YMin) / costRaster.meanCellHeight), # Bottom-most cell number
			costRaster.height - math.floor(max(0, costRaster.extent.YMax - currentFeature.extent.YMax) / costRaster.meanCellHeight), # Top-most cell number
		]
		extent.append(costRaster.extent.XMin + (extent[0] * costRaster.meanCellWidth)) # Lower left X coordinate
		extent.append(costRaster.extent.YMin + (extent[2] * costRaster.meanCellHeight)) # Lower left Y coordinate
		return extent
	
	def rasterCells(self, costRaster, currentFeature):
		extent = self.rasterCellExtent(costRaster, currentFeature)
		npValues = arcpy.RasterToNumPyArray(costRaster, arcpy.Point(extent[4], extent[5]), 1 + extent[3] - extent[2], 1 + extent[1] - extent[0], nodata_to_value = None)
		for r in range(extent[0], extent[1] + 1):
			leftEdge = costRaster.extent.XMin + (r * costRaster.meanCellWidth)
			rightEdge = leftEdge + costRaster.meanCellWidth
			rowIndex = r - extent[0]
			for c in range(extent[2], extent[3] + 1):
				val = npValues.item(rowIndex, c - extent[2])
				if not(val == None) and not(val == 0):
					bottomEdge = costRaster.extent.YMin + (c * costRaster.meanCellHeight)
					ex = arcpy.Extent(leftEdge, bottomEdge, rightEdge, bottomEdge + costRaster.meanCellHeight)
					yield (ex, val)
		

	def execute(self, parameters, messages):
		"""The source code of the tool."""
		featureClass = parameters[0].valueAsText
		costRaster = arcpy.Raster(parameters[2].valueAsText)
		searchCursor = arcpy.da.SearchCursor(featureClass, ['OID@', 'Shape@'])
		map = {}
		count = 0
		for row in searchCursor:
			count += 1
		
		searchCursor.reset()
		current = 0
		arcpy.SetProgressor("step", "Calculating polyline costs...", 0, current, count)
		for row in searchCursor:
			total = 0
			fullLength = row[1].length
			current += 1
			arcpy.SetProgressorLabel("Calculating for polyline #{0}".format(row[0]))
			for cell in self.rasterCells(costRaster, row[1]):
				clippedFeature = row[1].clip(cell[0])
				length = clippedFeature.length
				if length > 0:
					total += length * cell[1]
			map[row[0]] = total
			
			arcpy.SetProgressorPosition()
			
		arcpy.SetProgressor("step", "Updating costs in table...")
		with arcpy.da.UpdateCursor(featureClass, ['OID@', parameters[1].valueAsText]) as uCursor:
			for row in uCursor:
				row[1] = 0
				if row[0] in map:
					row[1] = map[row[0]]
				uCursor.updateRow(row)
		arcpy.SetParameterAsText(3, featureClass)
		
class ShortestPath(object):
	def __init__(self):
		"""Define the tool (tool name is the name of the class)."""
		self.label = "Determine Shortest Path"
		self.description = "Determine the shortest path between nodes using a polyline edge network that connects them."
		self.canRunInBackground = False
		self.category = "Utility Tools"

	def getParameterInfo(self):
		"""Define parameter definitions"""
		params = []
		params.append(arcpy.Parameter(
				displayName = "Features",
				category = "Edge Information",
				name = "edge_features",
				datatype = "GPFeatureLayer",
				parameterType = "Required",
				direction = "Input"
			)
		)
		params[0].filter.list = ["Polyline"]
		
		params.append(arcpy.Parameter(
				displayName = "Start Field",
				category = "Edge Information",
				name = "edge_left_field",
				datatype = "Field",
				parameterType = "Required",
				direction = "Input"
		))
		params[1].parameterDependencies = [params[0].name]
		
		params.append(arcpy.Parameter(
				displayName = "End Field",
				category = "Edge Information",
				name = "edge_right_field",
				datatype = "Field",
				parameterType = "Required",
				direction = "Input"
		))
		params[2].parameterDependencies = [params[0].name]
		
		params.append(arcpy.Parameter(
				displayName = "Cost Field",
				category = "Edge Information",
				name = "edge_cost_field",
				datatype = "Field",
				parameterType = "Required",
				direction = "Input"
		))
		params[3].parameterDependencies = [params[0].name]
		params[3].list = ["Double", "Float", "Single", "Short", "Long"]
		
		params.append(arcpy.Parameter(
				displayName = "Features",
				category = "Node Information",
				name = "node_features",
				datatype = "GPFeatureLayer",
				parameterType = "Required",
				direction = "Input"
		))
		params[4].filter.list = ["Point"]
		
		params.append(arcpy.Parameter(
				displayName = "Identifier Field",
				category = "Node Information",
				name = "node_id_field",
				datatype = "Field",
				parameterType = "Required",
				direction = "Input"
		))
		params[5].parameterDependencies = [params[4].name]
		
		params.append(arcpy.Parameter(
				displayName = "Transfer Cost Field",
				category = "Node Information",
				name = "node_cost_field",
				datatype = "Field",
				parameterType = "Optional",
				direction = "Input"
		))
		params[6].parameterDependencies = [params[4].name]
		params[6].list = ["Double", "Float", "Single", "Short", "Long"]
		
		params.append(arcpy.Parameter(
				displayName = "Output Workspace",
				name = "sp_table_workspace",
				datatype = "Workspace",
				parameterType = "Required",
				direction = "Input"
		))
		
		params.append(arcpy.Parameter(
				displayName = "Shortest Path Table",
				name = "sp_table_name",
				datatype = "String",
				parameterType = "Required",
				direction = "Input"
		))
		params.append(arcpy.Parameter(
				displayName = "Output Table",
				name = "out_Table",
				datatype = "DETable",
				parameterType = "Derived",
				direction = "Output"
		))
		
		
		return params

	def isLicensed(self):
		"""Set whether tool is licensed to execute."""
		return True

	def updateParameters(self, parameters):
		"""Modify the values and properties of parameters before internal
		validation is performed.  This method is called whenever a parameter
		has been changed."""
		return

	def updateMessages(self, parameters):
		"""Modify the messages created by internal validation for each tool
		parameter.  This method is called after internal validation."""
		return
		
	def createTable(self, parameters, messages):
		tableName = parameters[7].valueAsText + "/" + parameters[8].valueAsText
		fieldType = []
		costFieldType = []
		fields = arcpy.ListFields(parameters[4].valueAsText)
		for field in fields:
			if field.name == parameters[5].valueAsText:
				fieldType = [field.type, field.length]
		fields = arcpy.ListFields(parameters[0].valueAsText)
		for field in fields:
			if field.name == parameters[3].valueAsText:
				costFieldType = [field.type, field.length]
		if len(fieldType) == 0:
			messages.addWarning("Node ID field not found in node class")
			return False
		if len(costFieldType) == 0:
			messages.addWarning("Cost field not found in edge class")
			return False
		if arcpy.Exists(tableName):
			messages.addMessage("Removing existing table...")
			arcpy.Delete_management(tableName)
		arcpy.CreateTable_management(parameters[7].valueAsText, parameters[8].valueAsText)
		fields = [
			["StartNode", fieldType[0], fieldType[1], "Start Node", False],
			["EndNode", fieldType[0], fieldType[1], "End Node", False],
			["PathCost", costFieldType[0], costFieldType[1], "Cost", True],
			["NextNode", fieldType[0], fieldType[1], "Next Node", True]
		]
		for f in fields:
			if f[4]:
				arcpy.AddField_management(tableName, f[0], f[1], f[2], field_alias = f[3], field_is_nullable = "NULLABLE")
			else:
				arcpy.AddField_management(tableName, f[0], f[1], f[2], field_alias = f[3])
		messages.addMessage("Table created")
		arcpy.DeleteField_management(tableName, "Field1")
		return tableName
		
	def getPointList(self, tableName, parameters, messages):
		points = {}
		fields = [parameters[5].valueAsText]
		useCost = False
		if not(parameters[6].valueAsText == None) and len(parameters[6].valueAsText) > 0:
			fields.append(parameters[6].valueAsText)
			useCost = True
		with arcpy.da.SearchCursor(parameters[4].valueAsText, fields) as cursor:
			for row in cursor:				
				points[row[0]] = row[1] if useCost else 0
		return points
		
	def initializeRoutingTable(self, points):
		routingTable = {}
		for p1 in points:
			for p2 in points:
				if p1 == p2:
					routingTable[str(p1) + "-" + str(p2)] = [p1, p2, 0, None]
				else:
					routingTable[str(p1) + "-" + str(p2)] = [p1, p2, -1, None]
		return routingTable
		
	def saveRoutingTable(self, tableName, routingTable, messages):
		with arcpy.da.InsertCursor(tableName, ["StartNode", "EndNode", "PathCost", "NextNode"]) as inCursor:
			for entryKey in routingTable:
				entry = routingTable[entryKey]
				inCursor.insertRow((entry[0], entry[1], entry[2], entry[3] if not(entry[3] == None) else ""))
		return True
		
	def addEdges(self, routingTable, parameters, messages):
		fields = [parameters[1].valueAsText, parameters[2].valueAsText, parameters[3].valueAsText]
		with arcpy.da.SearchCursor(parameters[0].valueAsText, fields) as cursor:
			for row in cursor:
				key = str(row[0]) + "-" + str(row[1])
				if routingTable[key][2] == -1 or routingTable[key][2] > row[2]:
					routingTable[key][2] = row[2]
					routingTable[key][3] = row[1]
				key = str(row[1]) + "-" + str(row[0])
				if routingTable[key][2] == -1 or routingTable[key][2] > row[2]:
					routingTable[key][2] = row[2]
					routingTable[key][3] = row[0]
		
	def findShortestPaths(self, routingTable, points, m):
		for k in points:
			for i in points:
				for j in points:
					key1 = str(i) + "-" + str(j)
					key2 = str(i) + "-" + str(k)
					key3 = str(k) + "-" + str(j)
					if routingTable[key2][2] > -1 and routingTable[key3][2] > -1 and (routingTable[key1][2] == -1 or routingTable[key1][2] > (routingTable[key2][2] + routingTable[key3][2])):
						routingTable[key1][2] = routingTable[key2][2] + routingTable[key3][2]
						routingTable[key1][3] = routingTable[key2][3]
					

	def execute(self, parameters, messages):
		"""The source code of the tool."""
		tableName = self.createTable(parameters, messages)
		if not(tableName):
			return
		points = self.getPointList(tableName, parameters, messages)
		routingTable = self.initializeRoutingTable(points)
		self.addEdges(routingTable, parameters, messages)
		self.findShortestPaths(routingTable, points, messages)
		self.saveRoutingTable(tableName, routingTable, messages)
		arcpy.SetParameterAsText(9, tableName)
		
class AllocateProduction(object):
	def __init__(self):
		"""Define the tool (tool name is the name of the class)."""
		self.label = "Allocate Production"
		self.description = "Assign production from suppliers to consumers based on the lowest cost."
		self.canRunInBackground = False
		self.category = "Utility Tools"

	def getParameterInfo(self):
		"""Define parameter definitions"""
		params = []
		params.append(arcpy.Parameter(
				displayName = "Routing Network",
				name = "routing_network",
				datatype = "DETable",
				parameterType = "Required",
				direction = "Input"
			)
		)
		params.append(arcpy.Parameter(
				displayName = "Suppliers",
				category = "Supply",
				name = "suppliers_table",
				datatype = "DETable",
				parameterType = "Required",
				direction = "Input"
			)
		)
		params.append(arcpy.Parameter(
				displayName = "Location",
				category = "Supply",
				name = "supply_field",
				datatype = "Field",
				parameterType = "Required",
				direction = "Input"
		))
		params[2].parameterDependencies = [params[1].name]
		params.append(arcpy.Parameter(
				displayName = "Production Cost",
				category = "Supply",
				name = "cost_field",
				datatype = "Field",
				parameterType = "Required",
				direction = "Input"
		))
		params[3].parameterDependencies = [params[1].name]
		params[3].list = ["Double", "Float", "Single", "Short", "Long"]
		params.append(arcpy.Parameter(
				displayName = "Maximum Capacity",
				category = "Supply",
				name = "capacity_field",
				datatype = "Field",
				parameterType = "Optional",
				direction = "Input"
		))
		params[4].parameterDependencies = [params[1].name]
		params[4].list = ["Double", "Float", "Single", "Short", "Long"]
		params.append(arcpy.Parameter(
				displayName = "Consumers",
				category = "Consumption",
				name = "consumption_table",
				datatype = "DETable",
				parameterType = "Required",
				direction = "Input"
			)
		)
		params.append(arcpy.Parameter(
				displayName = "Location",
				category = "Consumption",
				name = "consumer_field",
				datatype = "Field",
				parameterType = "Required",
				direction = "Input"
		))
		params[6].parameterDependencies = [params[5].name]
		params.append(arcpy.Parameter(
				displayName = "Demand Amount",
				category = "Consumption",
				name = "demand_field",
				datatype = "Field",
				parameterType = "Optional",
				direction = "Input"
		))
		params[7].parameterDependencies = [params[5].name]
		params[7].list = ["Double", "Float", "Single", "Short", "Long"]
		params.append(arcpy.Parameter(
				displayName = "Priority",
				category = "Consumption",
				name = "priority_field",
				datatype = "Field",
				parameterType = "Optional",
				direction = "Input"
		))
		params[8].parameterDependencies = [params[5].name]
		params[8].list = ["Double", "Float", "Single", "Short", "Long"]

		params.append(arcpy.Parameter(
			displayName = "Travel Cost Factor",
			name = "cost_factor",
			datatype = "GPDouble",
			parameterType = "Optional",
			direction = "Input"
		))

		params.append(arcpy.Parameter(
			displayName = "Shipment Size",
			name = "shipment_factor",
			datatype = "GPDouble",
			parameterType = "Optional",
			direction = "Input"
		))

		params.append(arcpy.Parameter(
				displayName = "Output Workspace",
				name = "sp_table_workspace",
				datatype = "Workspace",
				parameterType = "Required",
				direction = "Input"
		))
		
		params.append(arcpy.Parameter(
				displayName = "Orders Table",
				name = "or_table_name",
				datatype = "String",
				parameterType = "Required",
				direction = "Input"
		))

		params.append(arcpy.Parameter(
				displayName = "Output Table",
				name = "out_Table",
				datatype = "DETable",
				parameterType = "Derived",
				direction = "Output"
		))

		return params

	def isLicensed(self):
		"""Set whether tool is licensed to execute."""
		return True

	def updateParameters(self, parameters):
		"""Modify the values and properties of parameters before internal
		validation is performed.  This method is called whenever a parameter
		has been changed."""
		return

	def updateMessages(self, parameters):
		"""Modify the messages created by internal validation for each tool
		parameter.  This method is called after internal validation."""
		return

	def getDistributors(self, parameters, messages):
		fields = [parameters[6].valueAsText]
		useDemand = False
		usePriority = False
		if not(parameters[7].valueAsText == None) and len(parameters[7].valueAsText) > 0:
			fields.append(parameters[7].valueAsText)
			useDemand = True
		if not(parameters[8].valueAsText == None) and len(parameters[8].valueAsText) > 0:
			fields.append(parameters[8].valueAsText)
			usePriority = True
		distributors = []
		with arcpy.da.SearchCursor(parameters[5].valueAsText, fields) as sCursor:
			for row in sCursor:
				distributors.append({
					"location": row[0],
					"demand": row[1] if useDemand and (row[1] >= 0) else -1,
					"priority": row[2] if usePriority and (row[2] >= 0) else -1
				})
		distributors.sort(key = lambda d: d["demand"], reverse = True)
		distributors.sort(key = lambda d: d["priority"], reverse = True)
		return distributors

	def getSuppliers(self, parameters, messages):
		fields = [parameters[2].valueAsText, parameters[3].valueAsText]
		useCapacity = False
		if not(parameters[4].valueAsText == None) and len(parameters[4].valueAsText) > 0:
			useCapacity = True
			fields.append(parameters[4].valueAsText)
		suppliers = []
		with arcpy.da.SearchCursor(parameters[1].valueAsText, fields) as sCursor:
			for row in sCursor:
				suppliers.append({
					"location": row[0],
					"cost": row[1],
					"capacity": row[2] if useCapacity and (row[2] >= 0) else -1,
					"capacityLeft": row[2] if useCapacity and (row[2] >= 0) else -1,
				})
		return suppliers

	def calculateSupplierCost(self, costFactor, shippingFactor, distributor, supplier, parameters, messages):
		with arcpy.da.SearchCursor(parameters[0].valueAsText, ["StartNode", "EndNode", "PathCost"], "StartNode = '" + supplier["location"] + "' AND EndNode = '" + distributor["location"] + "'") as sCursor:
			for row in sCursor:
				return ((row[2] * costFactor) / shippingFactor) + supplier["cost"]

	def pickSupplier(self, costFactor, shippingFactor, distributor, suppliers, parameters, messages):
		lowestCost = None
		bestSupplier = None
		for supplier in suppliers:
			if supplier["capacityLeft"] == -1 or distributor["demand"] == -1 or supplier["capacityLeft"] > distributor["demand"]:
				totalCost = self.calculateSupplierCost(costFactor, shippingFactor, distributor, supplier, parameters, messages)
				if (lowestCost == None) or (totalCost < lowestCost):
					lowestCost = totalCost
					bestSupplier = supplier
		return (bestSupplier, lowestCost)
			
	def createTable(self, parameters, messages):
		tableName = parameters[11].valueAsText + "/" + parameters[12].valueAsText
		fieldType = []
		costFieldType = []
		quantityFieldType = []
		fields = arcpy.ListFields(parameters[1].valueAsText)
		for field in fields:
			if field.name == parameters[2].valueAsText:
				fieldType = [field.type, field.length]
			if field.name == parameters[3].valueAsText:
				costFieldType = [field.type, field.length]
			if field.name == parameters[3].valueAsText:
				costFieldType = [field.type, field.length]
		if len(fieldType) == 0:
			messages.addWarning("Node ID field not found in node class")
			return False
		if len(costFieldType) == 0:
			messages.addWarning("Cost field not found in node class")
			return False
		if arcpy.Exists(tableName):
			messages.addMessage("Removing existing table...")
			arcpy.Delete_management(tableName)
		arcpy.CreateTable_management(parameters[11].valueAsText, parameters[12].valueAsText)
		fields = [
			["Supplier", fieldType[0], fieldType[1], "Supplier", False],
			["Consumer", fieldType[0], fieldType[1], "Consumer", False],
			["UnitCost", costFieldType[0], costFieldType[1], "Unit Cost", False],
			["Quantity", "LONG", None, "Quantity", False]
		]
		for f in fields:
			arcpy.AddField_management(tableName, f[0], f[1], f[2], field_alias = f[3])
		messages.addMessage("Table created")
		arcpy.DeleteField_management(tableName, "Field1")
		return tableName
	
	def execute(self, parameters, messages):
		"""The source code of the tool."""
		output = self.createTable(parameters, messages)
		costFactor = float(parameters[9].valueAsText) if not(parameters[9] == None) and len(parameters[9].valueAsText) > 0 else 1
		shippingFactor = float(parameters[10].valueAsText) if not(parameters[10] == None) and len(parameters[10].valueAsText) > 0 else 1
		distributors = self.getDistributors(parameters, messages)
		suppliers = self.getSuppliers(parameters, messages)
		orders = []
		for d in distributors:
			bestSupplier, unitCost = self.pickSupplier(costFactor, shippingFactor, d, suppliers, parameters, messages)
			if not(bestSupplier == None):
				if (bestSupplier["capacityLeft"] > -1) and (d["demand"] > -1):
					bestSupplier["capacityLeft"] -= d["demand"]
				orders.append({
					"supplier": bestSupplier["location"],
					"consumer": d["location"],
					"quantity": d["demand"],
					"unitCost": unitCost
				})
		with arcpy.da.InsertCursor(output, ["Supplier", "Consumer", "Quantity", "UnitCost"]) as inCursor:
			for order in orders:
				inCursor.insertRow((order["supplier"], order["consumer"], order["quantity"], order["unitCost"]))
		arcpy.SetParameterAsText(13, output)
