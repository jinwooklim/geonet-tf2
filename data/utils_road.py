# Mostly based on the code written by Tinghui Zhou: 
# https://github.com/tinghuiz/SfMLearner/blob/master/utils.py
from __future__ import division
import numpy as np
import tensorflow as tf
import math

def euler2mat(z, y, x):
  """Converts euler angles to rotation matrix
   TODO: remove the dimension for 'N' (deprecated for converting all source
         poses altogether)
   Reference: https://github.com/pulkitag/pycaffe-utils/blob/master/rot_utils.py#L174
  Args:
      z: rotation angle along z axis (in radians) -- size = [B, N]
      y: rotation angle along y axis (in radians) -- size = [B, N]
      x: rotation angle along x axis (in radians) -- size = [B, N]
  Returns:
      Rotation matrix corresponding to the euler angles -- size = [B, N, 3, 3]
  """
  B = tf.shape(z)[0]
  N = 1
  z = tf.clip_by_value(z, -np.pi, np.pi)
  y = tf.clip_by_value(y, -np.pi, np.pi)
  x = tf.clip_by_value(x, -np.pi, np.pi)

  # Expand to B x N x 1 x 1
  z = tf.expand_dims(tf.expand_dims(z, -1), -1)
  y = tf.expand_dims(tf.expand_dims(y, -1), -1)
  x = tf.expand_dims(tf.expand_dims(x, -1), -1)

  zeros = tf.zeros([B, N, 1, 1], tf.float64)
  ones  = tf.ones([B, N, 1, 1], tf.float64)

  cosz = tf.cos(z)
  sinz = tf.sin(z)
  rotz_1 = tf.concat([cosz, -sinz, zeros], axis=3)
  rotz_2 = tf.concat([sinz,  cosz, zeros], axis=3)
  rotz_3 = tf.concat([zeros, zeros, ones], axis=3)
  zmat = tf.concat([rotz_1, rotz_2, rotz_3], axis=2)

  cosy = tf.cos(y)
  siny = tf.sin(y)
  roty_1 = tf.concat([cosy, zeros, siny], axis=3)
  roty_2 = tf.concat([zeros, ones, zeros], axis=3)
  roty_3 = tf.concat([-siny,zeros, cosy], axis=3)
  ymat = tf.concat([roty_1, roty_2, roty_3], axis=2)

  cosx = tf.cos(x)
  sinx = tf.sin(x)
  rotx_1 = tf.concat([ones, zeros, zeros], axis=3)
  rotx_2 = tf.concat([zeros, cosx, -sinx], axis=3)
  rotx_3 = tf.concat([zeros, sinx, cosx], axis=3)
  xmat = tf.concat([rotx_1, rotx_2, rotx_3], axis=2)

  rotMat = tf.matmul(tf.matmul(xmat, ymat), zmat)
  return rotMat

def pose_vec2mat(vec):
  """Converts 6DoF parameters to transformation matrix
  Args:
      vec: 6DoF parameters in the order of tx, ty, tz, rx, ry, rz -- [B, 6]
  Returns:
      A transformation matrix -- [B, 4, 4]
  """
  batch_size, _ = vec.get_shape().as_list()
  translation = tf.slice(vec, [0, 0], [-1, 3])
  translation = tf.expand_dims(translation, -1)
  rx = tf.slice(vec, [0, 3], [-1, 1])
  ry = tf.slice(vec, [0, 4], [-1, 1])
  rz = tf.slice(vec, [0, 5], [-1, 1])
  rot_mat = euler2mat(rz, ry, rx)
  rot_mat = tf.squeeze(rot_mat, axis=[1])
  filler = tf.constant([0.0, 0.0, 0.0, 1.0], dtype=tf.float64, shape=[1, 1, 4])
  filler = tf.tile(filler, [batch_size, 1, 1])
  transform_mat = tf.concat([rot_mat, translation], axis=2)
  transform_mat = tf.concat([transform_mat, filler], axis=1)
  return transform_mat

# def pixel2cam(depth, pixel_coords, intrinsics, is_homogeneous=True):
#   """Transforms coordinates in the pixel frame to the camera frame.
#
#   Args:
#     depth: [batch, height, width]
#     pixel_coords: homogeneous pixel coordinates [batch, 3, height, width]
#     intrinsics: camera intrinsics [batch, 3, 3]
#     is_homogeneous: return in homogeneous coordinates
#   Returns:
#     Coords in the camera frame [batch, 3 (4 if homogeneous), height, width]
#   """
#   batch, height, width = depth.get_shape().as_list()
#   depth = tf.reshape(depth, [batch, 1, -1])
#   pixel_coords = tf.reshape(pixel_coords, [batch, 3, -1])
#   cam_coords = tf.matmul(tf.matrix_inverse(intrinsics), pixel_coords) * depth
#   if is_homogeneous:
#     ones = tf.ones([batch, 1, height*width])
#     cam_coords = tf.concat([cam_coords, ones], axis=1)
#   cam_coords = tf.reshape(cam_coords, [batch, -1, height, width])
#   return cam_coords


def pixel2cam(pixel_coords, intrinsics, is_homogeneous=True):
  """Transforms coordinates in the pixel frame to the camera frame.

  Args:
    pixel_coords: homogeneous pixel coordinates [batch, 3, height, width]
    intrinsics: camera intrinsics [batch, 3, 3]
    is_homogeneous: return in homogeneous coordinates
  Returns:
    Coords in the camera frame [batch, 3 (4 if homogeneous), height, width]
  """
  B, C, H, W = pixel_coords.get_shape().as_list()
  pixel_coords = tf.reshape(pixel_coords, [B, 3, -1])
  pixel_coords = tf.cast(pixel_coords, tf.float64)

  # unnorm_road_coords = tf.matmul(tf.matrix_inverse(intrinsics), pixel_coords)  # -- size = [B, 3, HxW]
  unnorm_road_coords = tf.matmul(tf.linalg.inv(intrinsics), pixel_coords)  # -- size = [B, 3, HxW]
  x_u = tf.slice(unnorm_road_coords, [0, 0, 0], [-1, 1, -1])  # -- size = [B, 1, HxW]
  y_u = tf.slice(unnorm_road_coords, [0, 1, 0], [-1, 1, -1])  # -- size = [B, 1, HxW]
  z_u = tf.slice(unnorm_road_coords, [0, 2, 0], [-1, 1, -1])  # -- size = [B, 1, HxW]

  la_road = y_u / -1.65
  # la_road = y_u / (dist_road)  # -- size = [B, 1, HxW]
  # la = np.zeros_like(la)
  x_n = x_u / (la_road + 1e-10)  # -- size = [B, 1, HxW]
  y_n = y_u / (la_road + 1e-10)  # -- size = [B, 1, HxW]
  z_n = z_u / (la_road + 1e-10)  # -- size = [B, 1, HxW]

  plane_coords = tf.concat([x_n, y_n, z_n], axis=1)  # -- size = [B, 3, HxW]
  # plane_coords = tf.reshape(plane_coords, [B, 3, H, W])  # -- size = [B, 3, H, W]

  if is_homogeneous:
    ones = tf.ones([B, 1, H * W], dtype=tf.float64)
    plane_coords = tf.concat([plane_coords, ones], axis=1)


  plane_coords = tf.reshape(plane_coords, [B, -1, H, W])
  # plane_coords = tf.transpose(plane_coords, [0, 2, 3, 1])  # -- size = [B, H, W, 3]
  return plane_coords, y_n

def cam2pixel(cam_coords, proj):
  """Transforms coordinates in a camera frame to the pixel frame.

  Args:
    cam_coords: [batch, 4, height, width]
    proj: [batch, 4, 4]
  Returns:
    Pixel coordinates projected from the camera frame [batch, height, width, 2]
  """
  batch, C, height, width = cam_coords.get_shape().as_list()
  cam_coords = tf.reshape(cam_coords, [batch, 4, -1])
  unnormalized_pixel_coords = tf.matmul(proj, cam_coords)
  x_u = tf.slice(unnormalized_pixel_coords, [0, 0, 0], [-1, 1, -1])
  y_u = tf.slice(unnormalized_pixel_coords, [0, 1, 0], [-1, 1, -1])
  z_u = tf.slice(unnormalized_pixel_coords, [0, 2, 0], [-1, 1, -1])
  x_n = x_u / (z_u + 1e-10)
  y_n = y_u / (z_u + 1e-10)
  pixel_coords = tf.concat([x_n, y_n], axis=1)
  pixel_coords = tf.reshape(pixel_coords, [batch, 2, height, width])
  return tf.transpose(pixel_coords, perm=[0, 2, 3, 1])

# def cam2pixel(cam_coords, proj):
#   """Transforms coordinates in a camera frame to the pixel frame.
#
#   Args:
#     cam_coords: [batch, 4, height, width]
#     proj: [batch, 4, 4]
#   Returns:
#     Pixel coordinates projected from the camera frame [batch, height, width, 2]
#   """
#   batch, height, width, _ = cam_coords.get_shape().as_list()
#   cam_coords = tf.reshape(cam_coords, [batch, 4, -1])
#   unnormalized_pixel_coords = tf.matmul(proj, cam_coords)
#   x_u = tf.slice(unnormalized_pixel_coords, [0, 0, 0], [-1, 1, -1])
#   y_u = tf.slice(unnormalized_pixel_coords, [0, 1, 0], [-1, 1, -1])
#   z_u = tf.slice(unnormalized_pixel_coords, [0, 2, 0], [-1, 1, -1])
#   x_n = x_u / (z_u + 1e-10)
#   y_n = y_u / (z_u + 1e-10)
#   pixel_coords = tf.concat([x_n, y_n], axis=1)
#   pixel_coords = tf.reshape(pixel_coords, [batch, 2, height, width])
#   return tf.transpose(pixel_coords, perm=[0, 2, 3, 1])

def meshgrid(batch, height, width, is_homogeneous=True):
  """Construct a 2D meshgrid.

  Args:
    batch: batch size
    height: height of the grid
    width: width of the grid
    is_homogeneous: whether to return in homogeneous coordinates
  Returns:
    x,y grid coordinates [batch, 2 (3 if homogeneous), height, width]
  """
  x_t = tf.matmul(tf.ones(shape=tf.stack([height, 1])),
                  tf.transpose(tf.expand_dims(
                      tf.linspace(-1.0, 1.0, width), 1), [1, 0]))
  y_t = tf.matmul(tf.expand_dims(tf.linspace(-1.0, 1.0, height), 1),
                  tf.ones(shape=tf.stack([1, width])))
  x_t = (x_t + 1.0) * 0.5 * tf.cast(width - 1, tf.float32)
  y_t = (y_t + 1.0) * 0.5 * tf.cast(height - 1, tf.float32)
  if is_homogeneous:
    ones = tf.ones_like(x_t)
    coords = tf.stack([x_t, y_t, ones], axis=0)
  else:
    coords = tf.stack([x_t, y_t], axis=0)
  coords = tf.tile(tf.expand_dims(coords, 0), [batch, 1, 1, 1])
  return coords

def flow_warp(src_img, flow):
  """ inverse warp a source image to the target image plane based on flow field
  Args:
    src_img: the source  image [batch, height_s, width_s, 3]
    flow: target image to source image flow [batch, height_t, width_t, 2]
  Returns:
    Source image inverse warped to the target image plane [batch, height_t, width_t, 3]
  """
  batch, height, width, _ = src_img.get_shape().as_list()
  tgt_pixel_coords = tf.transpose(meshgrid(batch, height, width, False),
                     [0, 2, 3, 1])
  src_pixel_coords = tf.cast(tgt_pixel_coords, tf.float64) + tf.cast(flow, tf.float64)
  output_img = bilinear_sampler(src_img, src_pixel_coords)
  return output_img

def compute_rigid_flow(depth, pose, intrinsics, reverse_pose=False):
  """Compute the rigid_bk flow from target image plane to source image

  Args:
    depth: depth map of the target image [batch, height_t, width_t]
    pose: target to source (or source to target if reverse_pose=True)
          camera transformation matrix [batch, 6], in the order of
          tx, ty, tz, rx, ry, rz;
    intrinsics: camera intrinsics [batch, 3, 3]
  Returns:
    Rigid flow from target image to source image [batch, height_t, width_t, 2]
  """
  batch, height, width, _ = depth.get_shape().as_list()
  # Convert pose vector to matrix
  pose = pose_vec2mat(pose)
  if reverse_pose:
    # pose = tf.matrix_inverse(pose)
    pose = tf.linalg.inv(pose)

  # Construct pixel grid coordinates
  pixel_coords = meshgrid(batch, height, width)
  tgt_pixel_coords = tf.transpose(pixel_coords[:,:2,:,:], [0, 2, 3, 1])

  # Convert pixel coordinates to the camera frame
  intrinsics = tf.cast(intrinsics, tf.float64)
  cam_coords, some = pixel2cam(pixel_coords, intrinsics) # cam_coords = pixel2cam(depth, pixel_coords, intrinsics)

  # Construct a 4x4 intrinsic matrix
  filler = tf.constant([0.0, 0.0, 0.0, 1.0], dtype=tf.float64, shape=[1, 1, 4])
  filler = tf.tile(filler, [batch, 1, 1])
  zeros = tf.zeros([batch, 3, 1], dtype=tf.float64)
  intrinsics = tf.concat([intrinsics, zeros], axis=2)
  intrinsics = tf.concat([intrinsics, filler], axis=1)

  # Get a 4x4 transformation matrix from 'target' camera frame to 'source'
  # pixel frame.
  proj_tgt_cam_to_src_pixel = tf.matmul(intrinsics, pose)
  src_pixel_coords = cam2pixel(cam_coords, proj_tgt_cam_to_src_pixel)
  tgt_pixel_coords = tf.cast(tgt_pixel_coords, tf.float64)
  rigid_flow = src_pixel_coords - tgt_pixel_coords
  return rigid_flow

def bilinear_sampler(imgs, coords):
  """Construct a new image by bilinear sampling from the input image.

  Points falling outside the source image boundary have value 0.

  Args:
    imgs: source image to be sampled from [batch, height_s, width_s, channels]
    coords: coordinates of source pixels to sample from [batch, height_t,
      width_t, 2]. height_t/width_t correspond to the dimensions of the output
      image (don't need to be the same as height_s/width_s). The two channels
      correspond to x and y coordinates respectively.
  Returns:
    A new sampled image [batch, height_t, width_t, channels]
  """
  def _repeat(x, n_repeats):
    rep = tf.transpose(
        tf.expand_dims(tf.ones(shape=tf.stack([
            n_repeats,
        ])), 1), [1, 0])
    rep = tf.cast(rep, 'float32')
    x = tf.matmul(tf.reshape(x, (-1, 1)), rep)
    return tf.reshape(x, [-1])

  with tf.name_scope('image_sampling'):
    coords_x, coords_y = tf.split(coords, [1, 1], axis=3)
    inp_size = imgs.get_shape()
    coord_size = coords.get_shape()
    out_size = coords.get_shape().as_list()
    out_size[3] = imgs.get_shape().as_list()[3]

    coords_x = tf.cast(coords_x, 'float32')
    coords_y = tf.cast(coords_y, 'float32')

    x0 = tf.floor(coords_x)
    x1 = x0 + 1
    y0 = tf.floor(coords_y)
    y1 = y0 + 1

    y_max = tf.cast(tf.shape(imgs)[1] - 1, 'float32')
    x_max = tf.cast(tf.shape(imgs)[2] - 1, 'float32')
    zero = tf.zeros([1], dtype='float32')

    x0_safe = tf.clip_by_value(x0, zero, x_max)
    y0_safe = tf.clip_by_value(y0, zero, y_max)
    x1_safe = tf.clip_by_value(x1, zero, x_max)
    y1_safe = tf.clip_by_value(y1, zero, y_max)

    ## bilinear interp weights, with points outside the grid having weight 0
    # wt_x0 = (x1 - coords_x) * tf.cast(tf.equal(x0, x0_safe), 'float32')
    # wt_x1 = (coords_x - x0) * tf.cast(tf.equal(x1, x1_safe), 'float32')
    # wt_y0 = (y1 - coords_y) * tf.cast(tf.equal(y0, y0_safe), 'float32')
    # wt_y1 = (coords_y - y0) * tf.cast(tf.equal(y1, y1_safe), 'float32')

    wt_x0 = x1_safe - coords_x
    wt_x1 = coords_x - x0_safe
    wt_y0 = y1_safe - coords_y
    wt_y1 = coords_y - y0_safe

    ## indices in the flat image to sample from
    dim2 = tf.cast(inp_size[2], 'float32')
    dim1 = tf.cast(inp_size[2] * inp_size[1], 'float32')
    base = tf.reshape(
        _repeat(
            tf.cast(tf.range(coord_size[0]), 'float32') * dim1,
            coord_size[1] * coord_size[2]),
        [out_size[0], out_size[1], out_size[2], 1])

    base_y0 = base + y0_safe * dim2
    base_y1 = base + y1_safe * dim2
    idx00 = tf.reshape(x0_safe + base_y0, [-1])
    idx01 = x0_safe + base_y1
    idx10 = x1_safe + base_y0
    idx11 = x1_safe + base_y1

    ## sample from imgs
    imgs_flat = tf.reshape(imgs, tf.stack([-1, inp_size[3]]))
    imgs_flat = tf.cast(imgs_flat, 'float32')
    im00 = tf.reshape(tf.gather(imgs_flat, tf.cast(idx00, 'int32')), out_size)
    im01 = tf.reshape(tf.gather(imgs_flat, tf.cast(idx01, 'int32')), out_size)
    im10 = tf.reshape(tf.gather(imgs_flat, tf.cast(idx10, 'int32')), out_size)
    im11 = tf.reshape(tf.gather(imgs_flat, tf.cast(idx11, 'int32')), out_size)

    w00 = wt_x0 * wt_y0
    w01 = wt_x0 * wt_y1
    w10 = wt_x1 * wt_y0
    w11 = wt_x1 * wt_y1

    output = tf.add_n([
        w00 * im00, w01 * im01,
        w10 * im10, w11 * im11
    ])
    return output



def get_relative_velosity_with_pred_poses(self, batch_seqlen_obd, pred_poses):
  L_car = 2.7
  cam_car = (math.pi / 180.0) * 90.0
  bias_steering = -0.0
  fps = 10.0
  alpha = 10000.0 / (36 * fps)
  beta = 0.000901
  gamma = 0.0
  delta = 0.05 * math.pi / 180.0 * -0.0062

  input_shape = batch_seqlen_obd.get_shape()

  # all_obd_1_list = []
  # all_angle_list = []

  batch_result = []
  # poses_batch_result = []
  for b in range(input_shape[0]):
    seq_result = []
    # poses_seq_result = []
    for s in range(input_shape[1]):
      nearly_zero = random.gauss(0.0, 0.001)
      # angle = -batch_seqlen_obd[b][s][1] * 0.05 * math.pi/180.0
      # speed = batch_seqlen_obd[b][s][0] * 10000.0 / 36.0 / fps
      angle = delta * (batch_seqlen_obd[b][s][1] - bias_steering)
      speed = alpha * batch_seqlen_obd[b][s][0] * tf.exp(beta * angle + gamma * batch_seqlen_obd[b][s][0])
      speed_x = speed * tf.sin(angle)
      speed_y = speed * tf.cos(angle)

      x = speed_x
      y = pred_poses[b][s][1]  # nearly_zero
      z = speed_y
      pitch = pred_poses[b][s][3]  # nearly_zero
      yaw = angle
      roll = pred_poses[b][s][5]  # nearly_zero

      # all_obd_1_list.append(-batch_seqlen_obd[b][s][1])
      # all_angle_list.append(yaw)
      seq_result.append([x, y, z, pitch, yaw, roll])
      # poses_seq_result.append([pred_poses[b][s][0], pred_poses[b][s][1], pred_poses[b][s][2], pred_poses[b][s][3], pred_poses[b][s][4],pred_poses[b][s][5]])

    seq_result = tf.stack(seq_result)
    # poses_seq_result = tf.stack(poses_seq_result)

    batch_result.append(seq_result)
    # poses_batch_result.append(poses_seq_result)

  # self.all_obd_1 = tf.stack(all_obd_1_list)
  # self.all_angle = tf.stack(all_angle_list)
  batch_result = tf.stack(batch_result)
  # poses_batch_result = tf.stack(poses_batch_result)

  ## MinMax
  ## Dont Use : It makes NaN
  # mm_x = self.MinMaxScaler(batch_result[:, :, 0], poses_batch_result[:, :, 0])
  # mm_z = self.MinMaxScaler(batch_result[:, :, 2], poses_batch_result[:, :, 2])
  # mm_yaw = self.MinMaxScaler(batch_result[:, :, 4], poses_batch_result[:, :, 4])
  # batch_result = tf.stack([mm_x, batch_result[:,:,1], mm_z, batch_result[:,:,3], mm_yaw, batch_result[:,:,5]], axis=2)

  return batch_result


def get_pose_by_obd(obd):
  fps = 9.64764  # 10.0
  alpha = 1.0 / (3.6 * fps)
  beta = 0.000901
  gamma = 0.0
  delta = 0.05 * math.pi / 180.0 * -0.0062
  L_car = 2.7
  bias_steering = 0.0
  angle_scale = 540.0 / 35.0

  seq_result = []
  a = obd[1] / angle_scale * np.pi / 180.0 + bias_steering
  s = obd[0] * alpha

  theta = obd[1] / angle_scale / L_car * s * np.pi / 180.0

  if theta < 0.000001:
    theta = 0.000001

  phy = 0.0
  tx = -2.0 / theta * np.sin(theta / 2.0) * s * np.sin(a + theta / 2.0 + phy)
  tz = 2.0 / theta * np.sin(theta / 2.0) * s * np.cos(a + theta / 2.0 + phy)

  seq_result.append([tx, 0.0, tz, 0.0, theta, 0.0])
  seq_result = tf.stack(seq_result)
  return seq_result


  # L_car = 2.7
  # cam_car = (math.pi / 180.0) * 90.0
  # bias_steering = -0.0
  # fps = 10.0
  # alpha = 10000.0 / (36 * fps)
  # beta = 0.000901
  # gamma = 0.0
  # delta = 0.05 * math.pi / 180.0 * -0.0062
  #
  # angle = delta * (obd[1] - bias_steering)
  # speed = alpha * obd[0] * np.exp(beta * angle + gamma * obd[0])
  # speed_x = speed * np.sin(angle)
  # speed_y = speed * np.cos(angle)
  #
  # seq_result = []
  # x = speed_x
  # y = 0.0 # pred_poses[b][s][1]  # nearly_zero
  # z = speed_y
  # pitch = 0.0 # pred_poses[b][s][3]  # nearly_zero
  # yaw = angle
  # roll = 0.0 # pred_poses[b][s][5]  # nearly_zero
  #
  # seq_result.append([x, y, z, pitch, yaw, roll])
  # seq_result = tf.stack(seq_result)

  return seq_result