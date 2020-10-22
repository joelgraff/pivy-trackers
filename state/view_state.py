# -*- coding: utf-8 -*-
#***********************************************************************
#* Copyright (c) 2018 Joel Graff <monograff76@gmail.com>               *
#*                                                                     *
#* This program is free software; you can redistribute it and/or modify*
#* it under the terms of the GNU Lesser General Public License (LGPL)  *
#* as published by the Free Software Foundation; either version 2 of   *
#* the License, or (at your option) any later version.                 *
#* for detail see the LICENCE text file.                               *
#*                                                                     *
#* This program is distributed in the hope that it will be useful,     *
#* but WITHOUT ANY WARRANTY; without even the implied warranty of      *
#* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the       *
#* GNU Library General Public License for more details.                *
#*                                                                     *
#* You should have received a copy of the GNU Library General Public   *
#* License along with this program; if not, write to the Free Software *
#* Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307*
#* USA                                                                 *
#*                                                                     *
#***********************************************************************
"""
View state class
"""

import math

from pivy import coin
from PySide import QtGui

from ..coin import coin_utils

from pivy_trackers import Singleton

_NEAR_ZERO = 10**-30

class ViewStateGlobalCallbacks():
    """
    View-level callbacks to manage view state based on input handling
    """
    def __init__(self):
        """
        Constructor
        """

        pass

class ViewState(metaclass=Singleton):
    """
    Class to track the current state of the active or specified view
    """

    view = None

    @staticmethod
    def global_view_mouse_event(arg):
        """
        Global mouse event to update view state
        """

        #clear the matrix to force a refresh at the start of every mouse event
        ViewState()._matrix = None

    def __init__(self, view=None):
        """
        ViewState constructor
        """

        assert(ViewState.view or view), \
            'ViewState.__init__(): Reference to 3DInventor view undefined.'

        self.view = view

        self.viewport = \
            view.getViewer().getSoRenderManager().getViewportRegion()

        self.sg_root = self.view.getSceneGraph()
        self.root = coin.SoSeparator()
        self.root.setName('VIEWSTATE_ROOT')

        self.geo_origin = None

        self.sg_root.insertChild(self.root, 0)

        self.active_task_panel = None
        self._matrix = None

        self.callbacks = {}

        self.add_mouse_event(
            ViewState.global_view_mouse_event)

    def set_geo_reference(self, system, coordinates):
        """
        Set the georeferencing parameters for the SoGeoOrigin
        """

        if not self.geo_origin:
            self.geo_origin = coin.SoGeoOrigin()
            self.geo_origin.setName('GEO_ORIGIN')
            self.root.insertChild(self.geo_origin, 0)

        self.geo_origin.geoSystem.setValues(system)
        self.geo_origin.geoCoords.setValue(
            coordinates[0], coordinates[1], coordinates[2])

    def dump(self, node=None):
        """
        Dump the scenegraph to console, unless node is specified
        """

        _node = node

        if not _node:
            _node = self.sg_root

        coin_utils.dump_node(_node)

    def get_matrix(self, node, parent=None, refresh=True):
        """
        Return the matrix for transfomations applied to the passed node

        node - the Coin3D SoNode with the desired transformation
        parent - optional - sg root default
        refresh - if false, retrieves last matrix
        """

        if not parent:
            parent = self.sg_root

        if not refresh:
            if self._matrix:
                return self._matrix

        #define the search path
        _search = coin.SoSearchAction()
        _search.setNode(node)
        _search.apply(parent)

        #get the matrix for the transformation
        _matrix = coin.SoGetMatrixAction(ViewState().viewport)
        _matrix.apply(_search.getPath())

        self._matrix = coin.SbMatrix(_matrix.getMatrix().getValue())

        return self._matrix

    def get_active_task_panel(self, refresh=False):
        """
        Return a reference to the task panel form currently displayed
        and save a reference to it in the active_task property
        """

        if self.active_task_panel and not refresh:
            return self.active_task_panel

        _form = self.getMainWindow().findChild(QtGui.QWidget, 'TaskPanel')

        self.active_task_panel = _form

        return _form

    def transform_points(self, points, matrix, refresh=True):
        """
        Transform selected points by the transformation matrix
        """

        #store the view state matrix if a valid node is passed.
        #subsequent calls with null node will re-use the last valid node matrix

        _matrix = matrix

        if _matrix is None:
            return points

        _xlate = [_v for _v in _matrix.getValue()[3]]

        if all([_v < _NEAR_ZERO for _v in _xlate]):
            return points

        if any(math.isnan(_v) for _v in _xlate):
            return points

        #append fourth point to each coordinate
        _pts = [_v + (1.0,) for _v in points]

        _s = 0
        _result = []

        #iterate the list, processing it in sets of four coordinates at a time
        while _s < len(_pts):

            _mat_pts = _pts[_s:_s + 4]

            _last_point = len(_mat_pts)

            #pad the list if less than four points
            for _i in range(len(_mat_pts), 4):
                _mat_pts.append((0.0, 0.0, 0.0, 1.0))

            #convert and transform
            _mat = coin.SbMatrix(_mat_pts)

            for _v in _mat.multRight(_matrix).getValue()[:_last_point]:
                _result.append(tuple(_v)[0:3])

            _s += 4

        return _result

    def remove_event_cb(self, callback, event_class):
        """
        Remove an event callback
        """

        if event_class not in self.callbacks:
            return

        _cbs = self.callbacks[event_class]

        if callback not in _cbs:
            return

        _cb = _cbs[callback]

        self.view.removeEventCallbackPivy(event_class.getClassTypeId(), _cb)

        del _cbs[callback]

    def add_event_cb(self, callback, event_class):
        """
        Add an event callback
        """

        if event_class not in self.callbacks:
            self.callbacks[event_class] = {}

        _cbs = self.callbacks[event_class]

        if callback in _cbs:
            return

        _cbs[callback] = self.view.addEventCallbackPivy(
            event_class.getClassTypeId(), callback)

    def remove_mouse_event(self, callback):
        """
        Wrapper for InventorView removeEventCallback()
        """

        self.remove_event_cb(callback, coin.SoLocation2Event)

    def remove_button_event(self, callback):
        """
        Wrapper for InventorView removeEventCallback()
        """

        self.remove_event_cb(callback, coin.SoMouseButtonEvent)

    def add_mouse_event(self, callback):
        """
        Wrapper for InventorView addEventCallback()
        """

        self.add_event_cb(callback, coin.SoLocation2Event)

    def add_button_event(self, callback):
        """
        Wrapper for Coin3D addEventCallback()
        """

        self.add_event_cb(callback, coin.SoMouseButtonEvent)

    def getPoint(self, pos):
        """
        Wrapper for InventorView getPoint()
        """

        _pos = tuple(pos)
        return tuple(self.view.getPoint(_pos[:2]))

    def getPointOnScreen(self, point):
        """
        Wrapper for InventorView getPointOnScreen()
        """

        _pt = tuple(point)

        if len(_pt) == 2:
            _pt += (0.0,)

        assert(len(_pt) == 3),\
            'Invalid coordinate. Expected tuple of three floats.'

        return self.view.getPointOnScreen(point[0], point[1], point[2])

    def getObjectInfo(self, pos):
        """
        Wrapper for InventorView getObjectInfo()
        """

        return self.view.getObjectInfo(tuple(pos))

    def getCursorPos(self):
        """
        Wrapper for InventorView getCursorPos()
        """

        return self.view.getCursorPos()

    @staticmethod
    def getMainWindow():
        """
        Return reference to main window
        """
        top = QtGui.QApplication.topLevelWidgets()

        for item in top:
            if item.metaObject().className() == 'Gui::MainWindow':
                return item

        raise RuntimeError('No main window found')

    def finish(self):
        """
        Cleanup
        """

        for _evt_cls in self.callbacks:
            for _cb in self.callbacks[_evt_cls]:

                if not _cb:
                    continue

                self.view.removeEventCallbackPivy(
                    _evt_cls.getClassTypeId(), _cb)


        self.view = None
        self.viewport = None
        self.sg_root = None
        self.active_task_panel = None
        self._matrix = None
        self.callbacks = {}

        Singleton.finish(ViewState)
