import sys
import os
sys.path.append(os.getcwd())
import tools.io_utils as io
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import dgl
import torch as th
from tqdm import tqdm
import json

def plot_graph(points, bif_id, indices, edges1, edges2):
    fig = plt.figure()
    ax = plt.axes(projection='3d')
    ax._axis3don = False

    minc = np.min(bif_id)
    maxc = np.max(bif_id)

    if minc == maxc:
        C = bif_id * 0
    else:
        C = (bif_id - minc) / (maxc - minc)

    cmap = cm.get_cmap("viridis")
    ax.scatter(points[:,0], points[:,1], points[:,2], color=cmap(C),            depthshade=0, s = 5)

    inlet = indices['inlet']
    ax.scatter(points[inlet,0], points[inlet,1], points[inlet,2],               color='green', depthshade=0, s = 60)

    outlets = indices['outlets']
    ax.scatter(points[outlets,0], points[outlets,1], points[outlets,2],color='red', depthshade=0, s = 60)

    for iedge in range(edges1.size):
        ax.plot3D([points[edges1[iedge],0],points[edges2[iedge],0]],
                  [points[edges1[iedge],1],points[edges2[iedge],1]],
                  [points[edges1[iedge],2],points[edges2[iedge],2]],
                   color = 'black', linewidth=0.2, alpha = 0.5)

    # ax.set_xlim([points[outlets[0],0]-0.1,points[outlets[0],0]+0.1])
    # ax.set_ylim([points[outlets[0],1]-0.1,points[outlets[0],1]+0.1])
    # ax.set_zlim([points[outlets[0],2]-0.1,points[outlets[0],2]+0.1])

    plt.show()

def generate_types(bif_id, indices):
    types = []
    inlet_mask = []
    outlet_mask = []
    for i, id in enumerate(bif_id):
        if id == -1:
            cur_type = 0
        else:
            cur_type = 1
        if i in indices['inlet']:
            cur_type = 2
        elif i in indices['outlets']:
            cur_type = 3
        types.append(cur_type)
        if cur_type == 2:
            inlet_mask.append(True)
        else:
            inlet_mask.append(False)
        if cur_type == 3:
            outlet_mask.append(True)
        else:
            outlet_mask.append(False)
    return th.nn.functional.one_hot(th.tensor(types)), inlet_mask, outlet_mask

def generate_edge_features(points, edges1, edges2):
    rel_position = []
    rel_position_norm = []
    nedges = len(edges1)
    for i in range(nedges):
        diff = points[edges2[i],:] - points[edges1[i],:]
        ndiff = np.linalg.norm(diff)
        rel_position.append(diff / ndiff)
        rel_position_norm.append(ndiff)
    return np.array(rel_position), rel_position_norm

def add_fields(graph, field, field_name, subsample_time = 1):
    timesteps = [float(t) for t in field]
    timesteps.sort()
    dt = (timesteps[1] - timesteps[0]) * subsample_time
    # we skip the first 100 timesteps
    offset = 0
    count = 0
    # we use the third timension for time
    field_t = th.zeros((list(field.values())[0].shape[0], 1, 
                        len(timesteps) - offset))
    for t in field:
        if count >= offset:
            f = th.tensor(field[t], dtype = th.float32)
            field_t[:,0,count - offset] = f
            # graph.ndata[field_name + '_{}'.format(count - offset)] = f
        count = count + 1
    graph.ndata[field_name] = field_t[:,:,::subsample_time]
    graph.ndata['dt'] = th.reshape(th.ones(graph.num_nodes(), 
                                   dtype = th.float32) * dt, (-1,1,1))

def find_outlets(edges1, edges2):
    outlets = []
    for e in edges2:
        if e not in edges1:
            outlets.append(e)
    return outlets

def remove_points(idxs_to_delete, idxs_to_replace, edges1, edges2, npoints):
    npoints_to_delete = len(idxs_to_delete)   

    for i in range(npoints_to_delete):
        i1 = np.where(edges1 == idxs_to_delete[i])[0]
        if (len(i1)) != 0:
            edges1[i1] = idxs_to_replace[i]

        i2 = np.where(edges2 == idxs_to_delete[i])[0]
        if (len(i2)) != 0:
            edges2[i2] = idxs_to_replace[i]

    edges_to_delete = np.where(edges1 == edges2)[0]
    edges1 = np.delete(edges1, edges_to_delete)
    edges2 = np.delete(edges2, edges_to_delete)

    sampled_indices = np.delete(np.arange(npoints), idxs_to_delete)
    for i in range(edges1.size):
        edges1[i] = np.where(sampled_indices == edges1[i])[0][0]
        edges2[i] = np.where(sampled_indices == edges2[i])[0][0]

    return sampled_indices, edges1, edges2

def resample_points(points, edges1, edges2, indices, perc_points_to_keep, 
                    remove_caps):

    def modify_edges(edges1, edges2, ipoint_to_delete, ipoint_to_replace):
        i1 = np.where(edges1 == ipoint_to_delete)[0]
        if len(i1) != 0:   
            edges1[i1] = ipoint_to_replace
        
        i2 = np.where(np.array(edges2) == ipoint_to_delete)[0]
        if len(i2) != 0:
            edges2[i2] = ipoint_to_replace
        return edges1, edges2
    npoints = points.shape[0]
    npoints_to_keep = int(npoints * perc_points_to_keep)
    ipoints_to_delete = []
    ipoints_to_replace = []

    new_outlets = []
    for ip in range(remove_caps):
        for inlet in indices['inlet']:
            ipoints_to_delete.append(inlet + ip)
            ipoints_to_replace.append(inlet + remove_caps)
            edges1, edges2 = modify_edges(edges1, edges2, 
                                          inlet + ip, inlet + remove_caps)
        for outlet in indices['outlets']:
            ipoints_to_delete.append(outlet - ip)
            ipoints_to_replace.append(outlet - remove_caps)  
            edges1, edges2 = modify_edges(edges1, edges2, 
                                          outlet - ip, outlet - remove_caps) 
    
    for outlet in indices['outlets']:
        new_outlets.append(outlet - remove_caps)

    indices['outlets'] = new_outlets

    for _ in range(npoints - npoints_to_keep):
        diff = np.linalg.norm(points[edges1,:] - points[edges2,:],
                              axis = 1)
        # we don't consider the points that we already deleted
        diff[np.where(diff < 1e-13)[0]] = np.inf
        mdiff = np.min(diff)
        mind = np.where(np.abs(diff - mdiff) < 1e-12)[0][0]

        if edges2[mind] not in new_outlets:
            ipoint_to_delete = edges2[mind]
            ipoint_to_replace = edges1[mind]
        else:
            ipoint_to_delete = edges1[mind]
            ipoint_to_replace = edges2[mind]

        edges1, edges2 = modify_edges(edges1, edges2, 
                                      ipoint_to_delete, ipoint_to_replace)

        ipoints_to_delete.append(ipoint_to_delete)
        ipoints_to_replace.append(ipoint_to_replace)    

    sampled_indices, edges1, edges2 = remove_points(ipoints_to_delete,
                                                    ipoints_to_replace, 
                                                    edges1, edges2,
                                                    npoints)

    points = np.delete(points, ipoints_to_delete, axis = 0)

    return sampled_indices, points, edges1, edges2, indices

def dijkstra_algorithm(nodes, edges1, edges2, index):
    nnodes = nodes.shape[0]
    tovisit = np.arange(0,nnodes)
    dists = np.ones((nnodes)) * np.infty
    prevs = np.ones((nnodes)) * (-1)
    b_edges = np.array([edges1,edges2]).transpose()

    dists[index] = 0
    while len(tovisit) != 0:
        minindex = -1
        minlen = np.infty
        for iinde in range(len(tovisit)):
            if dists[tovisit[iinde]] < minlen:
                minindex = iinde
                minlen = dists[tovisit[iinde]]

        curindex = tovisit[minindex]
        tovisit = np.delete(tovisit, minindex)

        # find neighbors of curindex
        inb = b_edges[np.where(b_edges[:,0] == curindex)[0],1]

        for neib in inb:
            if np.where(tovisit == neib)[0].size != 0:
                alt = dists[curindex] + np.linalg.norm(nodes[curindex,:] - \
                        nodes[neib,:])
                if alt < dists[neib]:
                    dists[neib] = alt
                    prevs[neib] = curindex
    if np.max(dists) == np.infty:
        fig = plt.figure()
        ax = plt.axes(projection='3d')
        ax.scatter(nodes[:,0], nodes[:,1], nodes[:,2], s = 0.5, c = 'black')
        idx = np.where(dists > 1e30)[0]
        ax.scatter(nodes[idx,0], nodes[idx,1], nodes[idx,2], c = 'red')
        plt.show()
        raise ValueError("Distance in Dijkstra is infinite for some reason. You can try to adjust resample parameters.")
    return dists, prevs

def generate_boundary_edges(points, indices, edges1, edges2): 
    npoints = points.shape[0]
    idxs = indices['inlet'] + indices['outlets']
    bedges1 = []
    bedges2 = []
    rel_positions = []
    dists = []
    types = []
    for index in idxs:
        d, _ = dijkstra_algorithm(points, edges1, edges2, index)
        if index in indices['inlet']:
            type = 1
        else:
            type = 2
        for ipoint in range(npoints):
            bedges1.append(index)
            bedges2.append(ipoint)
            rp = points[ipoint,:] - points[index,:]
            rel_positions.append(rp)
            if np.linalg.norm(rp) > 1e-12:
                rel_positions[-1] = rel_positions[-1] / np.linalg.norm(rp)
            dists.append(d[ipoint])
            types.append(type)

    # we only keep edges corresponding to the closest boundary node in graph
    # distance to reduce number of edges
    edges_to_delete = []

    for ipoint in range(npoints):
        cur_dists = dists[ipoint::npoints]
        min_dist = np.min(cur_dists)
        minidx = np.where(cur_dists == min_dist)[0][0]
        if min_dist < 1e-12:
            edges_to_delete.append(ipoint + minidx * npoints)
        i = ipoint
        while i < len(dists):
            if i != ipoint + minidx * npoints:
                edges_to_delete.append(i)
            i = i + npoints

    bedges1 = np.delete(np.array(bedges1), edges_to_delete)
    bedges2 = np.delete(np.array(bedges2), edges_to_delete)
    rel_positions = np.delete(np.array(rel_positions), edges_to_delete, 
                              axis = 0)
    dists = np.delete(np.array(dists), edges_to_delete)
    types = np.delete(np.array(types), edges_to_delete)

    return bedges1, bedges2, rel_positions, dists, list(types)

def create_continuity_mask(types):
    continuity_mask = [0]
    npoints = types.shape[0]
    for i in range(1,npoints-1):
        if types[i-1,0] == 1 and types[i,0] == 1 and types[i + 1,0]:
            continuity_mask.append(1)
        else:
            continuity_mask.append(0)
    continuity_mask.append(0)
    return continuity_mask

def create_junction_edges(points, bif_id, edges1, edges2):
    npoints = bif_id.size
    jun_inlet_mask = [0] * npoints
    jun_mask = [0] * npoints
    juncts_inlets = {}
    jedges1 = []
    jedges2 = []
    for ipoint in range(npoints - 1):
        if bif_id[ipoint] == -1 and bif_id[ipoint + 1] != -1:
            # we use the junction id as key and the junction idx as value
            if juncts_inlets.get(bif_id[ipoint + 1]) == None:
                juncts_inlets[bif_id[ipoint + 1]] = ipoint
                jun_inlet_mask[ipoint] = 1
                jun_mask[ipoint] = 1
        if bif_id[ipoint] == -1 and bif_id[ipoint - 1] != -1:
            # we look for the right inlet
            jedges1.append(juncts_inlets[bif_id[ipoint - 1]])
            jedges2.append(ipoint)
            jun_mask[ipoint] = 1
    masks = {'inlets': jun_inlet_mask, 'all': jun_mask}
    dists = {}
    for jun_id in juncts_inlets:
        d, _ = dijkstra_algorithm(points, edges1, edges2, juncts_inlets[jun_id])
        dists[juncts_inlets[jun_id]] = d

    jrel_position = []
    jdistance = []
    for iedg in range(len(jedges1)):
        jrel_position.append(points[jedges2[iedg],:] - points[jedges1[iedg],:])
        jdistance.append(dists[jedges1[iedg]][jedges2[iedg]])

    jrel_position = np.array(jrel_position)
    jdistance = np.array(jdistance)

    # make edges bidirectional
    jedges1_copy = jedges1.copy()
    jedges1 = jedges1 + jedges2
    jedges2 = jedges2 + jedges1_copy
    jrel_position = np.concatenate((jrel_position, -jrel_position), axis = 0)
    jdistance = np.concatenate((jdistance, jdistance))
    types = [3] * len(jedges1)
    return jedges1, jedges2, jrel_position, jdistance, types, masks

     
def generate_graph(file, input_dir, resample_perc, 
                   add_boundary_edges, add_junction_edges):
    soln = io.read_geo(input_dir + '/' + file)
    point_data, _, points = io.get_all_arrays(soln.GetOutput())
    edges1, edges2 = io.get_edges(soln.GetOutput())

    inlet = [0]
    outlets = find_outlets(edges1, edges2)

    indices = {'inlet': inlet,
               'outlets': outlets}

    sampled_indices, points, edges1, edges2, indices = resample_points(points,  
                                                              edges1, 
                                                              edges2, indices,
                                                              resample_perc,
                                                              remove_caps = 1)

    count = 0
    for outlet in indices['outlets']:
        iout = int(np.where(sampled_indices == outlet)[0])
        indices['outlets'][count] = iout
        count = count + 1

    bif_id = point_data['BifurcationId'][sampled_indices]
    try:
        area = list(io.gather_array(point_data, 'area').values())[0]
    except Exception as e:
        area = point_data['area']
    area = area[sampled_indices]

    # we manually make the graph bidirected in order to have the relative 
    # position of nodes make sense (xj - xi = - (xi - xj)). Otherwise, each edge
    # will have a single feature
    edges1_copy = edges1.copy()
    edges1 = np.concatenate((edges1, edges2))
    edges2 = np.concatenate((edges2, edges1_copy))

    rel_position, distance = generate_edge_features(points, edges1, edges2)
    etypes = [0] * edges1.size
    if add_boundary_edges:
        bedges1, bedges2, \
        brel_position, bdistance, \
        btypes = generate_boundary_edges(points, indices, edges1, edges2)
        edges1 = np.concatenate((edges1, bedges1))
        edges2 = np.concatenate((edges2, bedges2))
        etypes = etypes + btypes
        distance = np.concatenate((distance, bdistance))
        rel_position = np.concatenate((rel_position, brel_position), axis = 0)

    if add_junction_edges:
        jedges1, jedges2, \
        jrel_position, jdistance, \
        jtypes, jmasks = create_junction_edges(points, bif_id, edges1, edges2)
        edges1 = np.concatenate((edges1, jedges1))
        edges2 = np.concatenate((edges2, jedges2))
        etypes = etypes + jtypes
        distance = np.concatenate((distance, jdistance))
        rel_position = np.concatenate((rel_position, jrel_position), axis = 0)

    # plot_graph(points, bif_id, indices, edges1, edges2)   
    graph = dgl.graph((edges1, edges2), idtype = th.int32)

    graph.ndata['x'] = th.tensor(points, dtype = th.float32)
    graph.ndata['area'] = th.reshape(th.tensor(area, dtype = th.float32), 
                                     (-1,1,1))
    types, inlet_mask, \
    outlet_mask = generate_types(bif_id, indices)
    continuity_mask = create_continuity_mask(types)

    graph.ndata['type'] = th.unsqueeze(types, 2)
    graph.ndata['inlet_mask'] = th.tensor(inlet_mask, dtype = th.int8)
    graph.ndata['outlet_mask'] = th.tensor(outlet_mask, dtype = th.int8)
    graph.ndata['continuity_mask'] = th.tensor(continuity_mask, dtype = th.int8)
    graph.ndata['jun_inlet_mask'] = th.tensor(jmasks['inlets'], dtype = th.int8)
    graph.ndata['jun_mask'] = th.tensor(jmasks['all'], dtype = th.int8)

    graph.edata['rel_position'] = th.unsqueeze(th.tensor(rel_position, 
                                               dtype = th.float32), 2)
    graph.edata['distance'] = th.reshape(th.tensor(distance, 
                                         dtype = th.float32), (-1,1,1))
    if add_boundary_edges:
        etypes = th.nn.functional.one_hot(th.tensor(etypes))
        graph.edata['type'] = th.unsqueeze(etypes, 2)

    return graph, point_data, indices, sampled_indices

if __name__ == "__main__":
    data_location = io.data_location()
    input_dir = data_location + 'vtps_aortas'
    output_dir = data_location + 'graphs/'

    # if we provide timestep file then we need to rescale time in vtp
    try:
        rescale_time = True
        timesteps = json.load(open(input_dir + '/timesteps.json'))
    except:
        rescale_time = False

    files = os.listdir(input_dir)    

    print('Processing all files in {}'.format(input_dir))
    print('File list:')
    print(files)
    for file in tqdm(files, desc = 'Generating graphs', colour='green'):
        if '.vtp' in file:
            filename = file.replace('.vtp','.grph')
            
            resample_perc = 0.06
            success = False
            add_boundary_edges = True
            add_junction_edges = True
            while not success:
                if 1:
                    graph, point_data, indices, \
                    sampled_indices = generate_graph(file, input_dir, 
                                                     resample_perc,
                                                     add_boundary_edges,
                                                     add_junction_edges)
                    success = True
                # except Exception as e:
                #     print(e)
                #     resample_perc = np.min([resample_perc * 2, 1])
            
            pressure = io.gather_array(point_data, 'pressure')
            flowrate = io.gather_array(point_data, 'flow')
            if len(flowrate) == 0:
                flowrate = io.gather_array(point_data, 'velocity')
            
            if rescale_time:
                times = [t for t in pressure]
                timestep = float(timesteps[filename[:filename.find('.')]])
                for t in times:
                    pressure[t * timestep] = pressure[t]
                    flowrate[t * timestep] = flowrate[t]
                    del pressure[t]
                    del flowrate[t]

            # select indices and scale pressure to be mmHg
            for t in pressure:
                pressure[t] = pressure[t][sampled_indices]  / 1333.2
                flowrate[t] = flowrate[t][sampled_indices]

            add_fields(graph, pressure, 'pressure')
            add_fields(graph, flowrate, 'flowrate')

            dgl.save_graphs(output_dir + filename, graph)
