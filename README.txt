# ArcGIS Logistics Tools

This is a toolkit I made for GEOM 3005 at Carleton University in Fall 2018. All code here is written by me, with ample help from the arcpy documentation.


## Calculate Polyline Cost

This tool takes a polyline feature class, a cost surface raster (in some "cost unit" per unit distance), and a field on the polyline feature class. It then determines the total cost of traversing the polyline by multiplying the length of the line through each cell by the cell value (for a final unit of "cost unit").

To get sensible results, the distance unit needs to be the same as the projection linear unit. In addition, the cost surface raster and the polyline feature class must have the same spatial reference system. I've sped up the processing time by using the extent of the raster and polyline features to calculate each cell's extent and then manually clip the feature (without creating a polygon feature), but there is no checking that these are in the same reference system.

## Shortest Path

This tool is an implementation of the Floyd-Warshall shortest path algorithm for bidirectional graphs. It takes a feature class of polylines (edges) and of points (nodes). The start/end point of each polyline must be determined by a field on the polyline that can be related to a field on the point (i.e. there must be a Start and End field on the polyline with the value from a field on the point). There must also be a Cost field on the polyline, that can be calculated using Calculate Polyline Cost or another method. 

The output is a table with one row for every pair of point features. This row will contain the smallest sum of the cost of the edges needed to travel from one point feature to the other, as well as the name of the next node that needs to be travelled through to reach the destination.

## Allocate Production

This tool provides a simple method for allocating production from Suppliers to Consumers. Each consumer may provide a required quantity and a priority; they will be assigned a supplier in order of decreasing priority then decreasing required quantity. The supplier assigned is the one with the lowest total unit cost; total unit cost is determined by the production cost (from a field on the Supplier table) plus the unit transportation cost (defined as the total transportation cost from the supplier to the consumer using the Shortest Path tool, divided by the number of units that can be sent in a shipment; optionally multiplied by another cost factor if needed to change the units). Suppliers may also have a maximum capacity; they will not be assigned to a consumer unless they can fulfill the entire order.

The output is a table with one row for every consumer. It contains the supplier they have been assigned, the order quantity (or -1 if they did not have a requested quantity), and the cost per unit.