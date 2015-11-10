# Authors:
#     Loic Gouarin <loic.gouarin@math.u-psud.fr>
#     Benjamin Graille <benjamin.graille@math.u-psud.fr>
#
# License: BSD 3 clause

"""
Example of the cube in 3D
"""
from six.moves import range
import pyLBM
dico = {
    'box':{'x': [0, 2], 'y': [0, 2], 'z':[0, 2], 'label':list(range(6))},
    'space_step':0.5,
    'schemes':[{'velocities':list(range(19))}]
}
dom = pyLBM.Domain(dico)
print dom
dom.visualize(view_distance=True)
