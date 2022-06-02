from multiprocessing.connection import wait
from turtle import width


import minecraft_pb2_grpc
from minecraft_pb2 import *

from population import *

# Clear the map and fill with AIR and DIRT
def simpleClearMap():
    client.fillCube(FillCubeRequest(
    cube=Cube(
        min=Point(x=-10, y=4, z=-10),
        max=Point(x=110, y=maxHeight+10, z=110)
    ),
    type=AIR))

client.fillCube(FillCubeRequest( 
    cube=Cube(
        min=Point(x=-10, y=0, z=-10),
        max=Point(x=mapWidth+mapBegin[0]+10, y=3, z=mapLenght+mapBegin[2]+10)
    ),
    type=DIRT))

def main():

        # we clear the map at the beginning
        simpleClearMap()

        # initialise ou 2 populations
        redPopulation = Population('r',nbRedPopulation,REDSTONE_BLOCK)
        bluePopulation = Population('b',nbBluePopulation,DIAMOND_BLOCK)

        # We plan 100 cycles
        for c in range(100):
            print("Generation:", c)
            
            # with 20 updates
            for u in range(20):
                print("update:",u," red:",redPopulation.nbIndividual, " blue:",bluePopulation.nbIndividual)

                redPopulation.update(bluePopulation)
                bluePopulation.update(redPopulation)

            for pop in (redPopulation,bluePopulation):
                pop.cycle()

        exit()
main()