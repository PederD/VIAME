# ckwg +29
# Copyright 2019 by Kitware, Inc.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#  * Redistributions of source code must retain the above copyright notice,
#  this list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright notice,
#  this list of conditions and the following disclaimer in the documentation
#  and/or other materials provided with the distribution.
#
#  * Neither name of Kitware, Inc. nor the names of any contributors may be used
#  to endorse or promote products derived from this software without specific
#  prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS ``AS IS''
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE AUTHORS OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
# OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from __future__ import print_function
from __future__ import division

from vital.algo import TrainDetector

from vital.types import BoundingBox
from vital.types import CategoryHierarchy
from vital.types import DetectedObjectSet
from vital.types import DetectedObject

from PIL import Image

from distutils.util import strtobool
from shutil import copyfile

import argparse
import numpy as np
import torch
import pickle
import os
import signal
import sys

class MMDetTrainer( TrainDetector ):
  """
  Implementation of TrainDetector class
  """
  def __init__( self ):
    TrainDetector.__init__( self )

    self._config_file = ""
    self._seed_weights = ""
    self._train_directory = "deep_training"
    self._output_directory = "category_models"
    self._output_prefix = "custom_cfrnn"
    self._gpu_count = -1
    self._launcher = "none"    # "none, pytorch, slurm, or mpi" 
    self._random_seed = "none"
    self._validate = "false"
    self._tmp_annotation_file = "annotations.pickle"

  def get_configuration( self ):
    # Inherit from the base class
    cfg = super( TrainDetector, self ).get_configuration()

    cfg.set_value( "config_file", self._config_file )
    cfg.set_value( "seed_weights", self._seed_weights )
    cfg.set_value( "train_directory", self._train_directory )
    cfg.set_value( "output_directory", self._output_directory )
    cfg.set_value( "output_prefix", self._output_prefix )
    cfg.set_value( "gpu_count", str( self._gpu_count ) )
    cfg.set_value( "launcher", str( self._launcher ) )
    cfg.set_value( "random_seed", str( self._random_seed ) )
    cfg.set_value( "validate", str( self._validate ) )

    return cfg

  def set_configuration( self, cfg_in ):
    cfg = self.get_configuration()
    cfg.merge_config( cfg_in )

    self._config_file = str( cfg.get_value( "config_file" ) )
    self._seed_weights = str( cfg.get_value( "seed_weights" ) )
    self._train_directory = str( cfg.get_value( "train_directory" ) )
    self._output_directory = str( cfg.get_value( "output_directory" ) )
    self._output_prefix = str( cfg.get_value( "output_prefix" ) )
    self._gpu_count = int( cfg.get_value( "gpu_count" ) )
    self._launcher = str( cfg.get_value( "launcher" ) )
    self._validate = strtobool( cfg.get_value( "validate" ) )

    self._training_data = []

  def check_configuration( self, cfg ):
    if not cfg.has_value( "config_file" ) or len( cfg.get_value( "config_file") ) == 0:
      print( "A config file must be specified!" )
      return False
    return True

  def load_network( self ):

    train_config = "train_config.py"

    if len( self._train_directory ) > 0:
      if not os.path.exists( self._train_directory ):
        os.mkdir( self._train_directory )
      train_config = os.path.join( self._train_directory, train_config )

    self.insert_class_count( self_.config_file, train_config )

    from mmcv import Config
    self._cfg = Config.fromfile( train_config )

    if self._cfg.get( 'cudnn_benchmark', False ):
      torch.backends.cudnn.benchmark = True

    if self._train_directory is not None:
      self._cfg.work_dir = self._train_directory
      self._groundtruth_store = os.path.join(
        self._train_directory, self._tmp_annotation_file )
      if not os.path.exists( self._train_directory ):
        os.mkdir( self._train_directory )
    else:
      self._groundtruth_store = self._tmp_annotation_file

    if self._seed_weights is not None:
      self._cfg.resume_from = self._seed_weights

    if self._gpu_count > 0:
      self._cfg.gpus = self._gpu_count
    else:
      self._cfg.gpus = torch.cuda.device_count()

    if self._cfg.checkpoint_config is not None:
      from mmdet import __version__
      self._cfg.checkpoint_config.meta = dict(
        mmdet_version=__version__, config=self._cfg.text )

    if self._launcher == 'none':
      self._distributed = False
    else:
      self._distributed = True
      from mmdet.apis import init_dist
      init_dist( self._launcher, **self._cfg.dist_params )

    from mmdet.apis import get_root_logger
    self._logger = get_root_logger( self._cfg.log_level )
    self._logger.info( 'Distributed training: {}'.format( self._distributed ) )

    if self._random_seed is not "none":
      logger.info( 'Set random seed to {}'.format( self._random_seed ) )
      from mmdet.apis import set_random_seed
      set_random_seed( int( self._random_seed ) )

    from mmdet.models import build_detector

    self._model = build_detector(
      self._cfg.model, train_cfg=self._cfg.train_cfg, test_cfg=self._cfg.test_cfg )

  def add_data_from_disk( self, categories, train_files, train_dets, test_files, test_dets ):
    if len( train_files ) != len( train_dets ):
      print( "Error: train file and groundtruth count mismatch" )
      return

    self._categories = categories

    for filename, groundtruth in zip( train_files, train_dets ):
      entry = dict()

      im = Image.open( filename, 'r' )
      width, height = im.size

      if width <= 1 or height <= 1:
        continue

      annotations = dict()

      boxes = np.ndarray( ( 0, 4 ) )
      labels = np.ndarray( 0 )

      for i, item in enumerate( groundtruth ):

        obj_id = item.type().get_most_likely_class()

        if categories.has_class_id( obj_id ):

          obj_box = [ [ item.bounding_box().min_x(),
                        item.bounding_box().min_y(),
                        item.bounding_box().max_x(),
                        item.bounding_box().max_y() ] ]

          boxes = np.append( boxes, obj_box, axis = 0 )
          labels = np.append( labels, categories.get_class_id( obj_id ) + 1 )

      annotations["bboxes"] = boxes.astype( np.float32 )
      annotations["labels"] = labels.astype( np.int_ )

      entry["filename"] = filename
      entry["width"] = width
      entry["height"] = height
      entry["ann"] = annotations

      self._training_data.append( entry )

  def update_model( self ):

    self.load_network()

    with open( self._groundtruth_store, 'wb' ) as fp:
      pickle.dump( self._training_data, fp )

    from mmdet.datasets.custom import CustomDataset

    signal.signal( signal.SIGINT, lambda signal, frame: self.interupt_handler() )

    train_dataset = CustomDataset(
      self._groundtruth_store,
      '.',
      self._cfg.data.train.img_scale,
      self._cfg.data.train.img_norm_cfg,
      size_divisor = self._cfg.data.train.size_divisor,
      flip_ratio = self._cfg.data.train.flip_ratio,
      with_mask = self._cfg.data.train.with_mask,
      with_crowd = self._cfg.data.train.with_crowd,
      with_label = self._cfg.data.train.with_label )

    from mmdet.apis import train_detector

    train_detector(
      self._model,
      train_dataset,
      self._cfg,
      distributed = self._distributed,
      validate = self._validate,
      logger = self._logger )

    self.save_final_model()

  def interupt_handler( self ):
    self.save_final_model()
    sys.exit( 0 )

  def save_final_model( self ):
    output_cfg_file = self._output_prefix + ".py"
    output_wgt_file = self._output_prefix + ".pth"
    output_lbl_file = self._output_prefix + ".lbl"

    if len( self._output_directory ) > 0:
      if not os.path.exists( self._output_directory ):
        os.mkdir( self._output_directory )

      output_cfg_file = os.path.join( self._output_directory, output_cfg_file )
      output_wgt_file = os.path.join( self._output_directory, output_wgt_file )
      output_lbl_file = os.path.join( self._output_directory, output_lbl_file )

    self.insert_class_count( self_.config_file, output_cfg_file )
    copyfile( os.path.join( self._train_directory, "latest.pth" ), output_wgt_file )

    with open( output_lbl_file, "w" ) as fout:
      for category in self._categories:
        fout.write( category + "\n" )

  def insert_class_count( self, input_cfg, output_cfg ):

    repl_strs = [ [ "[-CLASS_COUNT_INSERT-]", str(len(self._categories)+1) ] ]

    fin = open( input_cfg )
    fout = open( output_cfg, 'w' )

    all_lines = []
    for s in list( fin ):
      all_lines.append( s )

    for repl in repl_strs:
      for i, s in enumerate( all_lines ):
        all_lines[i] = s.replace( repl[0], repl[1] )
    for s in all_lines:
      fout.write( s )

    fout.close()
    fin.close()


def __vital_algorithm_register__():
  from vital.algo import algorithm_factory

  # Register Algorithm
  implementation_name  = "mmdet"

  if algorithm_factory.has_algorithm_impl_name(
      MMDetTrainer.static_type_name(), implementation_name ):
    return

  algorithm_factory.add_algorithm( implementation_name,
    "PyTorch MMDet training routine", MMDetTrainer )

  algorithm_factory.mark_algorithm_as_loaded( implementation_name )
