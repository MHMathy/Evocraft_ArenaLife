import numpy as np
from re import I
from multiprocessing import Process
from minecraft_pb2 import *
import random

import minecraft_pb2_grpc
from minecraft_pb2 import *
import grpc

channel = grpc.insecure_channel('localhost:5001')
client = minecraft_pb2_grpc.MinecraftServiceStub(channel)

## Valeurs initiales
nbRedPopulation = 10
nbBluePopulation = 10
nbPopulationType = 2
mapBegin = [0,4,0]
mapWidth = 50
mapLenght = 50
maxHeight = 30

topParentFactor = 0.4
crossoverRate = 0.8
mutationFactor = 0.2
mutationRate = 0.05

# Reduce vector to have an axis with 1 value
def reduceVector(vector):
    m = max(abs(vector[0]),abs(vector[1]),abs(vector[2]))
    vector = (vector[0]/m,vector[1]/m,vector[2]/m)
    return vector

# Clamp value between given range
def clamp(n, smallest, largest):
    return max(smallest, min(n, largest))

# Returns distance between 2 3d points
def distance3D(pos1,pos2):
    return np.sqrt((pos2[0]-pos1[0])**2 + (pos2[1]-pos1[1])**2 + (pos2[2]-pos1[2])**2)

# Spawn blocks at given position with given height
def spawnBlockVerticalLine(x,y,z,h,type):
    client.fillCube(FillCubeRequest(  # Clear a 20x10x20 working area
    cube=Cube(
        min=Point(x=x, y=y, z=z),
        max=Point(x=x, y=y+h-1, z=z)
    ),
    type=type))

# Return the height of the first block corresponding to the given block type
def getBlockHeight(x,z,types):
    blocks = client.readCube(Cube(
        min=Point(x=x, y=0, z=z),
        max=Point(x=x, y=maxHeight, z=z)
    ))

    for i in range(len(blocks.blocks)):
        if blocks.blocks[i].type in types:
            return i

# An individual inside a population
# role of fighter: seek nearest enemy to kill
# role of breeder: seek nearest ally to breed 
class Individual:
    # id used to identify an individual
    id = 0
    def __init__(self,faction,blktype,type,pos,vita=0,parentId = []):
        Individual.id +=1
        self.id = Individual.id
        self.faction = faction
        self.blockType = blktype

        # 'r': random
        # 'f': fight
        # 'b': breed
        if type == 'r':
            self.type = random.choice(['f','b']) 
        else:
            self.type = type
        if vita != 0:
            self.vitality = vita
        else:
            self.vitality = random.randint(30,100)
        self.childrenPossible = 1
        self.nbKilled = 0
        self.timeAlive = 0
        self.familyId = parentId
        
        self.position = pos
        self.nextPosition = pos
        
    # Set position of an individual
    def setPosition(self,p):
        self.position = p

    # Display the individual with blocks
    def appear(self):
        l=0
        if self.type == 'f':
            l = 2
            
        elif self.type == 'b':
            l = 1

        spawnBlockVerticalLine(
            self.position[0],
            self.position[1],
            self.position[2],
            l,
            self.blockType)

    # Make an indivudal disappear
    def disappear(self):
        spawnBlockVerticalLine(
            self.position[0],
            self.position[1],
            self.position[2],
            2,
            AIR)
    
    # Update individual position
    # Determine if the individual lives, breeds or dies
    def update(self,allyPop,enemyPop): 

        next = (0,0,0)
        self.timeAlive += 1
        # if it's a fighter and enemies are alive
        if self.type == 'f'and enemyPop.nbIndividual!=0:
            closestEnemyId = 0
            closestEnemyDistance = 100000
            enemyToRemove = []

            for i in range(len(enemyPop.indArray)):
                enn = enemyPop.indArray[i]
                d = distance3D(self.position,enn.position)
                
                # try to find nearest enemy
                if d<closestEnemyDistance and d>1.5:
                    closestEnemyId = i 
                    closestEnemyDistance = d

                # if enemy is within one block range, it tries to kill
                elif d<1.5 and self.vitality<enn.vitality:
                        enemyToRemove.append(i)
                        enn.disappear()
            enemyP = enemyPop.indArray[closestEnemyId].position

            # remove enemies from enemy list
            for i in enemyToRemove[::-1]:
                self.nbKilled += 1
                enemyPop.indArray.pop(i)
                enemyPop.nbIndividual -=1
            
            # calculate next posision from enemy target
            next = (enemyP[0]-self.position[0],enemyP[1]-self.position[1],enemyP[2]-self.position[2])
            next = reduceVector(next)

        # if it's breeder who can still breed and there is still allies
        elif self.type == 'b' and self.childrenPossible > 0 and allyPop.nbIndividual > 1: 
            closestAllyId = 0
            closestAllyDistance = 100000
            
            # try to find nearest ally
            for i in range(len(allyPop.indArray)):
                ind = allyPop.indArray[i]

                # if ally is not itself and not from the same family
                if ind.id!=self.id and ind.id not in self.familyId:
                    d = distance3D(self.position,ind.position)

                    # tries to find nearest ally
                    if d<closestAllyDistance and d>1.5:
                        closestAllyId = i
                        closestAllyDistance = d

                    # if ally is within one block range, it tries to breed
                    elif d<1.5:
                        surrounding = client.readCube(Cube(
                            min=Point(x=self.position[0]-1, y=self.position[1], z=self.position[2]-1),
                            max=Point(x=self.position[0]+1, y=self.position[1], z=self.position[2]+1)
                        ))
                        availableSpot = []
                        # if there is room for the child, we create it
                        for p in surrounding.blocks:
                            if p.type == AIR:
                                availableSpot.append((p.position.x,p.position.y,p.position.z))
                        if len(availableSpot)>0:
                            p = random.choice(availableSpot)
                            child = Individual(
                                self.faction,
                                self.blockType,
                                'r',
                                p,
                                random.randint(min(self.vitality,ind.vitality),max(self.vitality,ind.vitality)),
                                [self.id,ind.id])
                            child.appear()
                            allyPop.indArray.append(child)
                            allyPop.nbIndividual += 1
                            self.familyId.append(child.id)
                            self.childrenPossible -=1

                            # once the breeder can't breed anymore, it becomes a fighter
                            if self.childrenPossible==0:
                                self.type = 'f'
                                self.vitality += 20

            # calculate next posision from ally target
            allyP = allyPop.indArray[closestAllyId].position
            next = ( allyP[0]-self.position[0],allyP[1]-self.position[1],allyP[2]-self.position[2])
            next = reduceVector(next)
        
        # determine if desired position is possible
        self.nextPosition = (
        int(self.position[0]+next[0]),
        self.position[1],
        int(self.position[2]+next[2]))

        nextBlock = client.readCube(Cube(
            min=Point(x=self.nextPosition[0], y=self.nextPosition[1], z=self.nextPosition[2]),
            max=Point(x=self.nextPosition[0], y=self.nextPosition[1], z=self.nextPosition[2])
        ))

        if nextBlock.blocks[0].type == AIR:
            self.disappear()
            self.position = self.nextPosition
            self.appear()
    

# A population is a grouping of individuals
# has a faction value
# a base and current number of individual
# a given blocktype for every individual of this population
class Population:
    def __init__(self,f,bNbI,bty):
        self.faction = f
        self.baseNbIndividual = bNbI
        self.nbIndividual = bNbI
        
        self.blockType = bty
        
        self.indArray = [Individual(f,bty,'r',(0,0,0)) for i in range(bNbI)]
        self.randomPopulationPosition()

    # Attribute random position to the population within the map
    def randomPopulationPosition(self):
        for ind in self.indArray:
            ind.disappear()
            rx = random.randint(mapBegin[0],mapBegin[0]+mapWidth)
            rz = random.randint(mapBegin[2],mapBegin[2]+mapLenght)
            ry = getBlockHeight(rx,rz,[AIR,WATER])
            ind.setPosition((rx,ry,rz))

    # Update the individuals if there is still anyone
    def update(self,enemyPop):
        if self.nbIndividual!=0:
            for i in range(self.nbIndividual):
                self.indArray[i].update(self,enemyPop)
    
    # Returns an array with every individuals position
    def getPositionArray(self):
        return [ind.position for ind in self.indArray]

    # Calculate the fitness a=of an individual
    @staticmethod
    def fitness(ind):
        #print("fitind", individual)
        return (ind.timeAlive + ind.nbKilled*2)

    # A cycle in the genetic algorithm
    def cycle(self):
        # Clear old individuals
        for ind in self.indArray:
            ind.disappear()

        # Calculate parent fitness
        if self.nbIndividual >=2:
            fitnessPopulation = [0]*self.nbIndividual
            fitParent = []

            for i in range(self.nbIndividual):
                fitnessPopulation[i] = Population.fitness(self.indArray[i])
                
            nbParent = clamp(int(self.nbIndividual*topParentFactor),2,100)
            print("choices", fitnessPopulation)

            # select fit parents
            fitParent = random.choices(self.indArray,weights=fitnessPopulation,k=nbParent)

            # Crossover
            nextGen = []
            for i in range(self.baseNbIndividual):
                if(random.randint(0,100)<crossoverRate*100):
                    parent = random.sample(fitParent,2)
                    vitality = random.choice([parent[0].vitality,parent[1].vitality])
                    nextGen.append(Individual(
                        self.faction,
                        self.blockType,
                        'r',
                        (0,0,0),
                        vitality))

                else:
                    nextGen.append(random.choice(fitParent))
            
            # Mutation
            for nInd in nextGen:
                if(random.randint(0,100)<mutationRate*100):
                    nInd.vitality = int(nInd.vitality * random.randrange(10-mutationFactor*10,10+mutationFactor*10)/10)
            self.indArray = nextGen
            self.nbIndividual = self.baseNbIndividual
        
        # if there is less than 2 parent alive, we reset the population with random
        else:
            self.indArray = [Individual(self.faction,self.blockType,'r',(0,0,0)) for i in range(self.baseNbIndividual)]
            self.nbIndividual = self.baseNbIndividual

        # set random position for every new individual
        self.randomPopulationPosition()
        



                
