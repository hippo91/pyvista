"""API description for managing plotting theme parameters in pyvista.

Examples
--------
Apply a built-in theme

>>> import pyvista as pv
>>> pv.set_plot_theme('default')
>>> pv.set_plot_theme('document')
>>> pv.set_plot_theme('dark')
>>> pv.set_plot_theme('paraview')

Load a theme into pyvista

>>> from pyvista.themes import DefaultTheme
>>> theme = DefaultTheme()
>>> theme.save('my_theme.json')  # doctest:+SKIP
>>> loaded_theme = pv.load_theme('my_theme.json')  # doctest:+SKIP

Create a custom theme from the default theme and load it into
pyvista.

>>> my_theme = DefaultTheme()
>>> my_theme.font.size = 20
>>> my_theme.font.title_size = 40
>>> my_theme.cmap = 'jet'
...
>>> pv.global_theme.load_theme(my_theme)
>>> pv.global_theme.font.size
20

"""

from enum import Enum
import json
import os
from typing import Callable, List, Optional, Union
import warnings

from ._typing import ColorLike, Number
from .plotting.colors import Color, get_cmap_safe, get_cycler
from .plotting.opts import InterpolationType
from .plotting.plotting import Plotter
from .plotting.tools import parse_font_family
from .utilities.misc import PyVistaDeprecationWarning


class _rcParams(dict):  # pragma: no cover
    """Reference to the deprecated rcParams dictionary."""

    def __getitem__(self, key):
        import pyvista  # avoids circular import

        warnings.warn(
            'rcParams is deprecated.  Please use ``pyvista.global_theme``.', DeprecationWarning
        )
        return getattr(pyvista.global_theme, key)

    def __setitem__(self, key, value):
        import pyvista  # avoids circular import

        warnings.warn(
            'rcParams is deprecated.  Please use ``pyvista.global_theme``.', DeprecationWarning
        )
        setattr(pyvista.global_theme, key, value)

    def __repr__(self):
        """Use the repr of global_theme."""
        import pyvista  # avoids circular import

        warnings.warn(
            'rcParams is deprecated.  Please use ``pyvista.global_theme``', DeprecationWarning
        )
        return repr(pyvista.global_theme)


def _check_between_zero_and_one(value: float, value_name: str = 'value'):
    """Check if a value is between zero and one."""
    if value < 0 or value > 1:
        raise ValueError(f'{value_name} must be between 0 and 1.')


def load_theme(filename):
    """Load a theme from a file.

    Parameters
    ----------
    filename : str
        Theme file. Must be json.

    Examples
    --------
    >>> import pyvista as pv
    >>> from pyvista.themes import DefaultTheme
    >>> theme = DefaultTheme()
    >>> theme.save('my_theme.json')  # doctest:+SKIP
    >>> loaded_theme = pv.load_theme('my_theme.json')  # doctest:+SKIP

    """
    with open(filename) as f:
        theme_dict = json.load(f)
    return DefaultTheme.from_dict(theme_dict)


def set_plot_theme(theme):
    """Set the plotting parameters to a predefined theme using a string.

    Parameters
    ----------
    theme : str
        Theme name.  Either ``'default'``, ``'document'``, ``'dark'``,
        or ``'paraview'``.

    Examples
    --------
    Set to the default theme.

    >>> import pyvista as pv
    >>> pv.set_plot_theme('default')

    Set to the document theme.

    >>> pv.set_plot_theme('document')

    Set to the dark theme.

    >>> pv.set_plot_theme('dark')

    Set to the ParaView theme.

    >>> pv.set_plot_theme('paraview')

    """
    import pyvista

    if isinstance(theme, str):
        theme = theme.lower()
        try:
            new_theme_type = _NATIVE_THEMES[theme].value
        except KeyError:
            raise ValueError(f"Theme {theme} not found in PyVista's native themes.")
        pyvista.global_theme.load_theme(new_theme_type())
    elif isinstance(theme, DefaultTheme):
        pyvista.global_theme.load_theme(theme)
    else:
        raise TypeError(
            f'Expected a ``pyvista.themes.DefaultTheme`` or ``str``, not '
            f'a {type(theme).__name__}'
        )


class _ThemeConfig:
    """Provide common methods for theme configuration classes."""

    __slots__: List[str] = []

    @classmethod
    def from_dict(cls, dict_):
        """Create from a dictionary."""
        inst = cls()
        for key, value in dict_.items():
            attr = getattr(inst, key)
            if hasattr(attr, 'from_dict'):
                setattr(inst, key, attr.from_dict(value))
            else:
                setattr(inst, key, value)
        return inst

    def to_dict(self) -> dict:
        """Return theme config parameters as a dictionary.

        Returns
        -------
        dict
            This theme parameter represented as a dictionary.

        """
        # remove the first underscore in each entry
        dict_ = {}
        for key in self.__slots__:
            value = getattr(self, key)
            key = key[1:]
            if hasattr(value, 'to_dict'):
                dict_[key] = value.to_dict()
            else:
                dict_[key] = value
        return dict_

    def __eq__(self, other):
        if not isinstance(self, type(other)):
            return False

        for attr_name in other.__slots__:
            attr = getattr(self, attr_name)
            other_attr = getattr(other, attr_name)
            if isinstance(attr, (tuple, list)):
                if tuple(attr) != tuple(other_attr):
                    return False
            else:
                if not attr == other_attr:
                    return False

        return True

    def __getitem__(self, key):
        """Get a value via a key.

        Implemented here for backwards compatibility.
        """
        return getattr(self, key)

    def __setitem__(self, key, value):
        """Set a value via a key.

        Implemented here for backwards compatibility.
        """
        setattr(self, key, value)


class _LightingConfig(_ThemeConfig):
    """PyVista lighting configuration.

    This will control the lighting interpolation type, parameters,
    and Physically Based Rendering (PBR) options

    Examples
    --------
    Set global PBR parameters.

    >>> import pyvista as pv
    >>> pv.global_theme.lighting_params.interpolation = 'pbr'
    >>> pv.global_theme.lighting_params.metallic = 0.5
    >>> pv.global_theme.lighting_params.roughness = 0.25

    """

    __slots__ = [
        '_interpolation',
        '_metallic',
        '_roughness',
        '_ambient',
        '_diffuse',
        '_specular',
        '_specular_power',
        '_emissive',
    ]

    def __init__(self):
        self._interpolation = InterpolationType.FLAT.value
        self._metallic = 0.0
        self._roughness = 0.5
        self._ambient = 0.0
        self._diffuse = 1.0
        self._specular = 0.0
        self._specular_power = 100.0
        self._emissive = False

    @property
    def interpolation(self) -> InterpolationType:
        """Return or set the default interpolation type.

        See :class:`pyvista.plotting.opts.InterpolationType`.

        Options are:

        * ``'Phong'``
        * ``'Flat'``
        * ``'Physically based rendering'``

        This is stored as a integer value of the ``InterpolationType``
        so that the theme can be JSON-serializable.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.lighting_params.interpolation = 'Phong'

        """
        return InterpolationType.from_any(self._interpolation)

    @interpolation.setter
    def interpolation(self, interpolation: Union[str, int, InterpolationType]):
        self._interpolation = InterpolationType.from_any(interpolation).value

    @property
    def metallic(self) -> float:
        """Return or set the metallic value.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.lighting_params.metallic = 0.5

        """
        return self._metallic

    @metallic.setter
    def metallic(self, metallic: float):
        self._metallic = metallic

    @property
    def roughness(self) -> float:
        """Return or set the roughness value.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.lighting_params.roughness = 0.25

        """
        return self._roughness

    @roughness.setter
    def roughness(self, roughness: float):
        self._roughness = roughness

    @property
    def ambient(self) -> float:
        """Return or set the ambient value."""
        return self._ambient

    @ambient.setter
    def ambient(self, ambient: float):
        self._ambient = ambient

    @property
    def diffuse(self) -> float:
        """Return or set the diffuse value."""
        return self._diffuse

    @diffuse.setter
    def diffuse(self, diffuse: float):
        self._diffuse = diffuse

    @property
    def specular(self) -> float:
        """Return or set the specular value."""
        return self._specular

    @specular.setter
    def specular(self, specular: float):
        self._specular = specular

    @property
    def specular_power(self) -> float:
        """Return or set the specular power value."""
        return self._specular_power

    @specular_power.setter
    def specular_power(self, specular_power: float):
        self._specular_power = specular_power

    @property
    def emissive(self) -> bool:
        """Return or set if emissive is used with point gaussian style."""
        return self._emissive

    @emissive.setter
    def emissive(self, emissive: bool):
        self._emissive = bool(emissive)


class _DepthPeelingConfig(_ThemeConfig):
    """PyVista depth peeling configuration.

    Examples
    --------
    Set global depth peeling parameters.

    >>> import pyvista as pv
    >>> pv.global_theme.depth_peeling.number_of_peels = 1
    >>> pv.global_theme.depth_peeling.occlusion_ratio = 0.0
    >>> pv.global_theme.depth_peeling.enabled = True

    """

    __slots__ = ['_number_of_peels', '_occlusion_ratio', '_enabled']

    def __init__(self):
        self._number_of_peels = 4
        self._occlusion_ratio = 0.0
        self._enabled = False

    @property
    def number_of_peels(self) -> int:
        """Return or set the number of peels in depth peeling.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.depth_peeling.number_of_peels = 1

        """
        return self._number_of_peels

    @number_of_peels.setter
    def number_of_peels(self, number_of_peels: int):
        self._number_of_peels = int(number_of_peels)

    @property
    def occlusion_ratio(self) -> float:
        """Return or set the occlusion ratio in depth peeling.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.depth_peeling.occlusion_ratio = 0.0

        """
        return self._occlusion_ratio

    @occlusion_ratio.setter
    def occlusion_ratio(self, occlusion_ratio: float):
        self._occlusion_ratio = float(occlusion_ratio)

    @property
    def enabled(self) -> bool:
        """Return or set if depth peeling is enabled.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.depth_peeling.enabled = True

        """
        return self._enabled

    @enabled.setter
    def enabled(self, enabled: bool):
        self._enabled = bool(enabled)

    def __repr__(self):
        txt = ['']
        parm = {
            'Number': 'number_of_peels',
            'Occlusion ratio': 'occlusion_ratio',
            'Enabled': 'enabled',
        }
        for name, attr in parm.items():
            setting = getattr(self, attr)
            txt.append(f'    {name:<21}: {setting}')
        return '\n'.join(txt)


class _SilhouetteConfig(_ThemeConfig):
    """PyVista silhouette configuration.

    Examples
    --------
    Set global silhouette parameters.

    >>> import pyvista as pv
    >>> pv.global_theme.silhouette.enabled = True
    >>> pv.global_theme.silhouette.color = 'grey'
    >>> pv.global_theme.silhouette.line_width = 2
    >>> pv.global_theme.silhouette.feature_angle = 20

    """

    __slots__ = ['_color', '_line_width', '_opacity', '_feature_angle', '_decimate', '_enabled']

    def __init__(self):
        self._color = Color('black')
        self._line_width = 2
        self._opacity = 1.0
        self._feature_angle = None
        self._decimate = None
        self._enabled = False

    @property
    def enabled(self) -> bool:
        """Return or set whether silhouette is on or off."""
        return self._enabled

    @enabled.setter
    def enabled(self, enabled: bool):
        self._enabled = bool(enabled)

    @property
    def color(self) -> Color:
        """Return or set the silhouette color.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.silhouette.color = 'red'

        """
        return self._color

    @color.setter
    def color(self, color: ColorLike):
        self._color = Color(color)

    @property
    def line_width(self) -> float:
        """Return or set the silhouette line width.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.silhouette.line_width = 2.0

        """
        return self._line_width

    @line_width.setter
    def line_width(self, line_width: float):
        self._line_width = float(line_width)

    @property
    def opacity(self) -> float:
        """Return or set the silhouette opacity.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.silhouette.opacity = 1.0

        """
        return self._opacity

    @opacity.setter
    def opacity(self, opacity: float):
        _check_between_zero_and_one(opacity, 'opacity')
        self._opacity = float(opacity)

    @property
    def feature_angle(self) -> Union[float, None]:
        """Return or set the silhouette feature angle.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.silhouette.feature_angle = 20.0

        """
        return self._feature_angle

    @feature_angle.setter
    def feature_angle(self, feature_angle: Union[float, None]):
        self._feature_angle = feature_angle

    @property
    def decimate(self) -> float:
        """Return or set the amount to decimate the silhouette.

        Parameter must be between 0 and 1.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.silhouette.decimate = 0.9

        """
        return self._decimate

    @decimate.setter
    def decimate(self, decimate: float):
        if decimate is None:
            self._decimate = None
        else:
            _check_between_zero_and_one(decimate, 'decimate')
            self._decimate = float(decimate)

    def __repr__(self):
        txt = ['']
        parm = {
            'Color': 'color',
            'Line width': 'line_width',
            'Opacity': 'opacity',
            'Feature angle': 'feature_angle',
            'Decimate': 'decimate',
        }
        for name, attr in parm.items():
            setting = getattr(self, attr)
            txt.append(f'    {name:<21}: {setting}')
        return '\n'.join(txt)


class _ColorbarConfig(_ThemeConfig):
    """PyVista colorbar configuration.

    Examples
    --------
    Set the colorbar width.

    >>> import pyvista as pv
    >>> pv.global_theme.colorbar_horizontal.width = 0.2

    """

    __slots__ = ['_width', '_height', '_position_x', '_position_y']

    def __init__(self):
        self._width = None
        self._height = None
        self._position_x = None
        self._position_y = None

    @property
    def width(self) -> float:
        """Return or set colorbar width.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.colorbar_horizontal.width = 0.2

        """
        return self._width

    @width.setter
    def width(self, width: float):
        self._width = float(width)

    @property
    def height(self) -> float:
        """Return or set colorbar height.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.colorbar_horizontal.height = 0.2

        """
        return self._height

    @height.setter
    def height(self, height: float):
        self._height = float(height)

    @property
    def position_x(self) -> float:
        """Return or set colorbar x position.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.colorbar_horizontal.position_x = 0.2

        """
        return self._position_x

    @position_x.setter
    def position_x(self, position_x: float):
        self._position_x = float(position_x)

    @property
    def position_y(self) -> float:
        """Return or set colorbar y position.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.colorbar_horizontal.position_y = 0.2

        """
        return self._position_y

    @position_y.setter
    def position_y(self, position_y: float):
        self._position_y = float(position_y)

    def __repr__(self):
        txt = ['']
        parm = {
            'Width': 'width',
            'Height': 'height',
            'X Position': 'position_x',
            'Y Position': 'position_y',
        }
        for name, attr in parm.items():
            setting = getattr(self, attr)
            txt.append(f'    {name:<21}: {setting}')

        return '\n'.join(txt)


class _AxesConfig(_ThemeConfig):
    """PyVista axes configuration.

    Examples
    --------
    Set the x axis color to black.

    >>> import pyvista as pv
    >>> pv.global_theme.axes.x_color = 'black'

    Show axes by default.

    >>> pv.global_theme.axes.show = True

    Use the ``vtk.vtkCubeAxesActor``.

    >>> pv.global_theme.axes.box = True

    """

    __slots__ = ['_x_color', '_y_color', '_z_color', '_box', '_show']

    def __init__(self):
        self._x_color = Color('tomato')
        self._y_color = Color('seagreen')
        self._z_color = Color('mediumblue')
        self._box = False
        self._show = True

    def __repr__(self):
        txt = ['Axes configuration']
        parm = {
            'X Color': 'x_color',
            'Y Color': 'y_color',
            'Z Color': 'z_color',
            'Use Box': 'box',
            'Show': 'show',
        }
        for name, attr in parm.items():
            setting = getattr(self, attr)
            txt.append(f'    {name:<21}: {setting}')

        return '\n'.join(txt)

    @property
    def x_color(self) -> Color:
        """Return or set x axis color.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.axes.x_color = 'red'
        """
        return self._x_color

    @x_color.setter
    def x_color(self, color: ColorLike):
        self._x_color = Color(color)

    @property
    def y_color(self) -> Color:
        """Return or set y axis color.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.axes.y_color = 'red'
        """
        return self._y_color

    @y_color.setter
    def y_color(self, color: ColorLike):
        self._y_color = Color(color)

    @property
    def z_color(self) -> Color:
        """Return or set z axis color.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.axes.z_color = 'red'
        """
        return self._z_color

    @z_color.setter
    def z_color(self, color: ColorLike):
        self._z_color = Color(color)

    @property
    def box(self) -> bool:
        """Use the ``vtk.vtkCubeAxesActor`` instead of the default ``vtk.vtkAxesActor``.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.axes.box = True

        """
        return self._box

    @box.setter
    def box(self, box: bool):
        self._box = bool(box)

    @property
    def show(self) -> bool:
        """Show or hide the axes actor.

        Examples
        --------
        Hide the axes by default.

        >>> import pyvista as pv
        >>> pv.global_theme.axes.show = False

        """
        return self._show

    @show.setter
    def show(self, show: bool):
        self._show = bool(show)


class _Font(_ThemeConfig):
    """PyVista plotter font configuration.

    Examples
    --------
    Set the default font family to 'arial'.  Must be either
    'arial', 'courier', or 'times'.

    >>> import pyvista as pv
    >>> pv.global_theme.font.family = 'arial'

    Set the default font size to 20.

    >>> pv.global_theme.font.size = 20

    Set the default title size to 40

    >>> pv.global_theme.font.title_size = 40

    Set the default label size to 10

    >>> pv.global_theme.font.label_size = 10

    Set the default text color to 'grey'

    >>> pv.global_theme.font.color = 'grey'

    Set the string formatter used to format numerical data to '%.6e'

    >>> pv.global_theme.font.fmt = '%.6e'

    """

    __slots__ = ['_family', '_size', '_title_size', '_label_size', '_color', '_fmt']

    def __init__(self):
        self._family = 'arial'
        self._size = 12
        self._title_size = None
        self._label_size = None
        self._color = Color('white')
        self._fmt = None

    def __repr__(self):
        txt = ['']
        parm = {
            'Family': 'family',
            'Size': 'size',
            'Title size': 'title_size',
            'Label size': 'label_size',
            'Color': 'color',
            'Float format': 'fmt',
        }
        for name, attr in parm.items():
            setting = getattr(self, attr)
            txt.append(f'    {name:<21}: {setting}')

        return '\n'.join(txt)

    @property
    def family(self) -> str:
        """Return or set the font family.

        Must be one of the following:

        * ``"arial"``
        * ``"courier"``
        * ``"times"``

        Examples
        --------
        Set the default global font family to 'courier'.

        >>> import pyvista as pv
        >>> pv.global_theme.font.family = 'courier'

        """
        return self._family

    @family.setter
    def family(self, family: str):
        parse_font_family(family)  # check valid font
        self._family = family

    @property
    def size(self) -> int:
        """Return or set the font size.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.font.size = 20

        """
        return self._size

    @size.setter
    def size(self, size: int):
        self._size = int(size)

    @property
    def title_size(self) -> int:
        """Return or set the title size.

        If ``None``, then VTK uses ``UnconstrainedFontSizeOn`` for titles.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.font.title_size = 20
        """
        return self._title_size

    @title_size.setter
    def title_size(self, title_size: int):
        if title_size is None:
            self._title_size = None
        else:
            self._title_size = int(title_size)

    @property
    def label_size(self) -> int:
        """Return or set the label size.

        If ``None``, then VTK uses ``UnconstrainedFontSizeOn`` for labels.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.font.label_size = 20
        """
        return self._label_size

    @label_size.setter
    def label_size(self, label_size: int):
        if label_size is None:
            self._label_size = None
        else:
            self._label_size = int(label_size)

    @property
    def color(self) -> Color:
        """Return or set the font color.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.font.color = 'black'
        """
        return self._color

    @color.setter
    def color(self, color: ColorLike):
        self._color = Color(color)

    @property
    def fmt(self) -> str:
        """Return or set the string formatter used to format numerical data.

        Examples
        --------
        Set the string formatter used to format numerical data to '%.6e'.

        >>> import pyvista as pv
        >>> pv.global_theme.font.fmt = '%.6e'

        """
        return self._fmt

    @fmt.setter
    def fmt(self, fmt: str):
        self._fmt = fmt


class _SliderStyleConfig(_ThemeConfig):
    """PyVista configuration for a single slider style."""

    __slots__ = [
        '_name',
        '_slider_length',
        '_slider_width',
        '_slider_color',
        '_tube_width',
        '_tube_color',
        '_cap_opacity',
        '_cap_length',
        '_cap_width',
    ]

    def __init__(self):
        """Initialize the slider style configuration."""
        self._name = None
        self._slider_length = None
        self._slider_width = None
        self._slider_color = None
        self._tube_width = None
        self._tube_color = None
        self._cap_opacity = None
        self._cap_length = None
        self._cap_width = None

    @property
    def name(self) -> str:
        """Return the name of the slider style configuration."""
        return self._name

    @name.setter
    def name(self, name: str):
        self._name = name

    @property
    def cap_width(self) -> float:
        """Return or set the cap width.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.slider_styles.modern.cap_width = 0.02

        """
        return self._cap_width

    @cap_width.setter
    def cap_width(self, cap_width: float):
        self._cap_width = float(cap_width)

    @property
    def cap_length(self) -> float:
        """Return or set the cap length.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.slider_styles.modern.cap_length = 0.01

        """
        return self._cap_length

    @cap_length.setter
    def cap_length(self, cap_length: float):
        self._cap_length = float(cap_length)

    @property
    def cap_opacity(self) -> float:
        """Return or set the cap opacity.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.slider_styles.modern.cap_opacity = 1.0

        """
        return self._cap_opacity

    @cap_opacity.setter
    def cap_opacity(self, cap_opacity: float):
        self._cap_opacity = float(cap_opacity)

    @property
    def tube_color(self) -> Color:
        """Return or set the tube color.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.slider_styles.modern.tube_color = 'black'
        """
        return self._tube_color

    @tube_color.setter
    def tube_color(self, tube_color: ColorLike):
        self._tube_color = Color(tube_color)

    @property
    def tube_width(self) -> float:
        """Return or set the tube_width.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.slider_styles.modern.tube_width = 0.005

        """
        return self._tube_width

    @tube_width.setter
    def tube_width(self, tube_width: float):
        self._tube_width = float(tube_width)

    @property
    def slider_color(self) -> Color:
        """Return or set the slider color.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.slider_styles.modern.slider_color = 'grey'

        """
        return self._slider_color

    @slider_color.setter
    def slider_color(self, slider_color: ColorLike):
        self._slider_color = Color(slider_color)

    @property
    def slider_width(self) -> float:
        """Return or set the slider width.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.slider_styles.modern.slider_width = 0.04

        """
        return self._slider_width

    @slider_width.setter
    def slider_width(self, slider_width: float):
        self._slider_width = float(slider_width)

    @property
    def slider_length(self) -> float:
        """Return or set the slider_length.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.slider_styles.modern.slider_length = 0.02

        """
        return self._slider_length

    @slider_length.setter
    def slider_length(self, slider_length: float):
        self._slider_length = float(slider_length)

    def __repr__(self):
        txt = ['']
        parm = {
            'Slider length': 'slider_length',
            'Slider width': 'slider_width',
            'Slider color': 'slider_color',
            'Tube width': 'tube_width',
            'Tube color': 'tube_color',
            'Cap opacity': 'cap_opacity',
            'Cap length': 'cap_length',
            'Cap width': 'cap_width',
        }
        for name, attr in parm.items():
            setting = getattr(self, attr)
            txt.append(f'        {name:<17}: {setting}')
        return '\n'.join(txt)


class _SliderConfig(_ThemeConfig):
    """PyVista configuration encompassing all slider styles.

    Examples
    --------
    Set the classic slider configuration.

    >>> import pyvista as pv
    >>> pv.global_theme.slider_styles.classic.slider_length = 0.02
    >>> pv.global_theme.slider_styles.classic.slider_width = 0.04
    >>> pv.global_theme.slider_styles.classic.slider_color = (0.5, 0.5, 0.5)
    >>> pv.global_theme.slider_styles.classic.tube_width = 0.005
    >>> pv.global_theme.slider_styles.classic.tube_color = (1.0, 1.0, 1.0)
    >>> pv.global_theme.slider_styles.classic.cap_opacity = 1
    >>> pv.global_theme.slider_styles.classic.cap_length = 0.01
    >>> pv.global_theme.slider_styles.classic.cap_width = 0.02

    Set the modern slider configuration.

    >>> pv.global_theme.slider_styles.modern.slider_length = 0.02
    >>> pv.global_theme.slider_styles.modern.slider_width = 0.04
    >>> pv.global_theme.slider_styles.modern.slider_color = (0.43, 0.44, 0.45)
    >>> pv.global_theme.slider_styles.modern.tube_width = 0.04
    >>> pv.global_theme.slider_styles.modern.tube_color = (0.69, 0.70, 0.709)
    >>> pv.global_theme.slider_styles.modern.cap_opacity = 0
    >>> pv.global_theme.slider_styles.modern.cap_length = 0.01
    >>> pv.global_theme.slider_styles.modern.cap_width = 0.02

    """

    __slots__ = ['_classic', '_modern']

    def __init__(self):
        """Initialize the slider configuration."""
        self._classic = _SliderStyleConfig()
        self._classic.name = 'classic'
        self._classic.slider_length = 0.02
        self._classic.slider_width = 0.04
        self._classic.slider_color = 'gray'
        self._classic.tube_width = 0.005
        self._classic.tube_color = 'white'
        self._classic.cap_opacity = 1
        self._classic.cap_length = 0.01
        self._classic.cap_width = 0.02

        self._modern = _SliderStyleConfig()
        self._modern.name = 'modern'
        self._modern.slider_length = 0.02
        self._modern.slider_width = 0.04
        self._modern.slider_color = (110, 113, 117)
        self._modern.tube_width = 0.04
        self._modern.tube_color = (178, 179, 181)
        self._modern.cap_opacity = 0
        self._modern.cap_length = 0.01
        self._modern.cap_width = 0.02

    @property
    def classic(self) -> _SliderStyleConfig:
        """Return the Classic slider configuration."""
        return self._classic

    @classic.setter
    def classic(self, config: _SliderStyleConfig):
        if not isinstance(config, _SliderStyleConfig):
            raise TypeError('Configuration type must be `_SliderStyleConfig`')
        self._classic = config

    @property
    def modern(self) -> _SliderStyleConfig:
        """Return the Modern slider configuration."""
        return self._modern

    @modern.setter
    def modern(self, config: _SliderStyleConfig):
        if not isinstance(config, _SliderStyleConfig):
            raise TypeError('Configuration type must be `_SliderStyleConfig`')
        self._modern = config

    def __repr__(self):
        txt = ['']
        parm = {
            'Classic': 'classic',
            'Modern': 'modern',
        }
        for name, attr in parm.items():
            setting = getattr(self, attr)
            txt.append(f'    {name:<21}: {setting}')
        return '\n'.join(txt)

    def __iter__(self):
        for style in [self._classic, self._modern]:
            yield style.name


class _TrameConfig(_ThemeConfig):
    """PyVista Trame configuration.

    Examples
    --------
    Set global trame view parameters.

    >>> import pyvista as pv
    >>> pv.global_theme.trame.interactive_ratio = 2
    >>> pv.global_theme.trame.still_ratio = 2

    """

    __slots__ = [
        '_interactive_ratio',
        '_still_ratio',
        '_jupyter_server_name',
        '_jupyter_server_port',
        '_server_proxy_enabled',
        '_server_proxy_prefix',
        '_default_mode',
        '_enable_vtk_warnings',
    ]

    def __init__(self):
        self._interactive_ratio = 1
        self._still_ratio = 1
        self._jupyter_server_name = 'pyvista-jupyter'
        self._jupyter_server_port = 0
        self._server_proxy_enabled = 'PYVISTA_TRAME_SERVER_PROXY_PREFIX' in os.environ
        # default for ``jupyter-server-proxy``
        self._server_proxy_prefix = os.environ.get('PYVISTA_TRAME_SERVER_PROXY_PREFIX', '/proxy/')
        self._default_mode = 'trame'
        self._enable_vtk_warnings = (
            os.environ.get('VTK_ENABLE_SERIALIZER_WARNINGS', 'false').lower() == 'true'
        )

    @property
    def interactive_ratio(self) -> Number:
        """Return or set the interactive ratio for PyVista Trame views.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.trame.interactive_ratio = 2

        """
        return self._interactive_ratio

    @interactive_ratio.setter
    def interactive_ratio(self, interactive_ratio: Number):
        self._interactive_ratio = interactive_ratio

    @property
    def still_ratio(self) -> Number:
        """Return or set the still ratio for PyVista Trame views.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.trame.still_ratio = 2

        """
        return self._still_ratio

    @still_ratio.setter
    def still_ratio(self, still_ratio: Number):
        self._still_ratio = still_ratio

    @property
    def jupyter_server_name(self):
        """Return or set the trame server name PyVista uses in Jupyter.

        This defaults to ``'pyvista-jupyter'``.

        This must be set before running :func:`pyvista.set_jupyter_backend`
        to ensure a server of this name is launched.

        Most users should not need to modify this.

        """
        return self._jupyter_server_name

    @jupyter_server_name.setter
    def jupyter_server_name(self, name: str):
        self._jupyter_server_name = name

    @property
    def jupyter_server_port(self) -> int:
        """Return or set the port for the Trame Jupyter server."""
        return self._jupyter_server_port

    @jupyter_server_port.setter
    def jupyter_server_port(self, port: int):
        self._jupyter_server_port = port

    @property
    def server_proxy_enabled(self) -> bool:
        """Return or set if use of relative URLs is enabled for the Jupyter interface."""
        return self._server_proxy_enabled

    @server_proxy_enabled.setter
    def server_proxy_enabled(self, enabled: bool):
        self._server_proxy_enabled = bool(enabled)

    @property
    def server_proxy_prefix(self):
        """Return or set URL prefix when using relative URLs with the Jupyter interface."""
        return self._server_proxy_prefix

    @server_proxy_prefix.setter
    def server_proxy_prefix(self, prefix: str):
        self._server_proxy_prefix = prefix

    @property
    def default_mode(self):
        """Return or set the default mode of the Trame backend.

        * ``'trame'``: Uses a view that can switch between client and server
          rendering modes.
        * ``'server'``: Uses a view that is purely server rendering.
        * ``'client'``: Uses a view that is purely client rendering (generally
          safe without a virtual frame buffer)

        """
        return self._default_mode

    @default_mode.setter
    def default_mode(self, mode: str):
        self._default_mode = mode

    @property
    def enable_vtk_warnings(self) -> bool:
        """Return or set if VTK web serializer warnings are enabled."""
        return self._enable_vtk_warnings

    @enable_vtk_warnings.setter
    def enable_vtk_warnings(self, enabled: bool):
        self._enable_vtk_warnings = bool(enabled)


class DefaultTheme(_ThemeConfig):
    """PyVista default theme.

    Examples
    --------
    Change the global default background color to white.

    >>> import pyvista as pv
    >>> pv.global_theme.color = 'white'

    Show edges by default.

    >>> pv.global_theme.show_edges = True

    Create a new theme from the default theme and apply it globally.

    >>> from pyvista.themes import DefaultTheme
    >>> my_theme = DefaultTheme()
    >>> my_theme.color = 'red'
    >>> my_theme.background = 'white'
    >>> pv.global_theme.load_theme(my_theme)

    """

    __slots__ = [
        '_name',
        '_background',
        '_jupyter_backend',
        '_trame',
        '_full_screen',
        '_window_size',
        '_image_scale',
        '_camera',
        '_notebook',
        '_font',
        '_auto_close',
        '_cmap',
        '_color',
        '_color_cycler',
        '_above_range_color',
        '_below_range_color',
        '_nan_color',
        '_edge_color',
        '_line_width',
        '_point_size',
        '_outline_color',
        '_floor_color',
        '_colorbar_orientation',
        '_colorbar_horizontal',
        '_colorbar_vertical',
        '_show_scalar_bar',
        '_show_edges',
        '_show_vertices',
        '_lighting',
        '_interactive',
        '_render_points_as_spheres',
        '_render_lines_as_tubes',
        '_transparent_background',
        '_title',
        '_axes',
        '_multi_samples',
        '_multi_rendering_splitting_position',
        '_volume_mapper',
        '_smooth_shading',
        '_depth_peeling',
        '_silhouette',
        '_slider_styles',
        '_return_cpos',
        '_hidden_line_removal',
        '_anti_aliasing',
        '_enable_camera_orientation_widget',
        '_split_sharp_edges',
        '_sharp_edges_feature_angle',
        '_before_close_callback',
        '_lighting_params',
        '_interpolate_before_map',
        '_opacity',
    ]

    def __init__(self):
        """Initialize the theme."""
        self._name = 'default'
        self._background = Color([0.3, 0.3, 0.3])
        self._full_screen = False
        self._camera = {
            'position': [1, 1, 1],
            'viewup': [0, 0, 1],
        }

        self._notebook = None
        self._window_size = [1024, 768]
        self._image_scale = 1
        self._font = _Font()
        self._cmap = 'viridis'
        self._color = Color('white')
        self._color_cycler = None
        self._nan_color = Color('darkgray')
        self._above_range_color = Color('grey')
        self._below_range_color = Color('grey')
        self._edge_color = Color('black')
        self._line_width = 1.0
        self._point_size = 5.0
        self._outline_color = Color('white')
        self._floor_color = Color('gray')
        self._colorbar_orientation = 'horizontal'

        self._colorbar_horizontal = _ColorbarConfig()
        self._colorbar_horizontal.width = 0.6
        self._colorbar_horizontal.height = 0.08
        self._colorbar_horizontal.position_x = 0.35
        self._colorbar_horizontal.position_y = 0.05

        self._colorbar_vertical = _ColorbarConfig()
        self._colorbar_vertical.width = 0.08
        self._colorbar_vertical.height = 0.45
        self._colorbar_vertical.position_x = 0.9
        self._colorbar_vertical.position_y = 0.02

        self._show_scalar_bar = True
        self._show_edges = False
        self._show_vertices = False
        self._lighting = True
        self._interactive = False
        self._render_points_as_spheres = False
        self._render_lines_as_tubes = False
        self._transparent_background = False
        self._title = 'PyVista'
        self._axes = _AxesConfig()
        self._split_sharp_edges = False
        self._sharp_edges_feature_angle = 30.0
        self._before_close_callback = None

        # Grab system flag for anti-aliasing
        try:
            self._multi_samples = int(os.environ.get('PYVISTA_MULTI_SAMPLES', 4))
        except ValueError:  # pragma: no cover
            self._multi_samples = 4

        # Grab system flag for auto-closing
        self._auto_close = os.environ.get('PYVISTA_AUTO_CLOSE', '').lower() != 'false'

        self._jupyter_backend = os.environ.get('PYVISTA_JUPYTER_BACKEND', 'trame')
        self._trame = _TrameConfig()

        self._multi_rendering_splitting_position = None
        self._volume_mapper = 'fixed_point' if os.name == 'nt' else 'smart'
        self._smooth_shading = False
        self._depth_peeling = _DepthPeelingConfig()
        self._silhouette = _SilhouetteConfig()
        self._slider_styles = _SliderConfig()
        self._return_cpos = True
        self._hidden_line_removal = False
        self._anti_aliasing = None
        self._enable_camera_orientation_widget = False

        self._lighting_params = _LightingConfig()
        self._interpolate_before_map = True
        self._opacity = 1.0

    @property
    def hidden_line_removal(self) -> bool:
        """Return or set hidden line removal.

        Wireframe geometry will be drawn using hidden line removal if
        the rendering engine supports it.

        See Also
        --------
        pyvista.Plotter.enable_hidden_line_removal

        Examples
        --------
        Enable hidden line removal.

        >>> import pyvista as pv
        >>> pv.global_theme.hidden_line_removal = True
        >>> pv.global_theme.hidden_line_removal
        True

        """
        return self._hidden_line_removal

    @hidden_line_removal.setter
    def hidden_line_removal(self, value: bool):
        self._hidden_line_removal = value

    @property
    def interpolate_before_map(self) -> bool:
        """Return or set whether to interpolate colors before mapping.

        If the ``interpolate_before_map`` is turned off, the color
        mapping occurs at polygon points and colors are interpolated,
        which is generally less accurate whereas if the
        ``interpolate_before_map`` is on (the default), then the scalars
        will be interpolated across the topology of the dataset which is
        more accurate.

        See Also
        --------
        :ref:`interpolate_before_mapping_example`

        Examples
        --------
        Enable hidden line removal.

        >>> import pyvista as pv

        Load a cylinder which has cells with a wide spread

        >>> cyl = pv.Cylinder(direction=(0, 0, 1), height=2).elevation()

        Common display argument to make sure all else is constant

        >>> dargs = dict(scalars='Elevation', cmap='rainbow', show_edges=True)

        >>> p = pv.Plotter(shape=(1, 2))
        >>> _ = p.add_mesh(
        ...     cyl,
        ...     interpolate_before_map=False,
        ...     scalar_bar_args={'title': 'Elevation - interpolated'},
        ...     **dargs
        ... )
        >>> p.subplot(0, 1)
        >>> _ = p.add_mesh(
        ...     cyl,
        ...     interpolate_before_map=True,
        ...     scalar_bar_args={'title': 'Elevation - interpolated'},
        ...     **dargs
        ... )
        >>> p.link_views()
        >>> p.camera_position = [(-1.67, -5.10, 2.06), (0.0, 0.0, 0.0), (0.00, 0.37, 0.93)]
        >>> p.show()  # doctest: +SKIP

        """
        return self._interpolate_before_map

    @interpolate_before_map.setter
    def interpolate_before_map(self, value: bool):
        self._interpolate_before_map = value

    @property
    def opacity(self) -> float:
        """Return or set the opacity.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.opacity = 0.5

        """
        return self._opacity

    @opacity.setter
    def opacity(self, opacity: float):
        _check_between_zero_and_one(opacity, 'opacity')
        self._opacity = float(opacity)

    @property
    def above_range_color(self) -> Color:
        """Return or set the default above range color.

        Examples
        --------
        Set the above range color to red.

        >>> import pyvista as pv
        >>> pv.global_theme.above_range_color = 'r'
        >>> pv.global_theme.above_range_color
        Color(name='red', hex='#ff0000ff', opacity=255)

        """
        return self._above_range_color

    @above_range_color.setter
    def above_range_color(self, value: ColorLike):
        self._above_range_color = Color(value)

    @property
    def below_range_color(self) -> Color:
        """Return or set the default below range color.

        Examples
        --------
        Set the below range color to blue.

        >>> import pyvista as pv
        >>> pv.global_theme.below_range_color = 'b'
        >>> pv.global_theme.below_range_color
        Color(name='blue', hex='#0000ffff', opacity=255)

        """
        return self._below_range_color

    @below_range_color.setter
    def below_range_color(self, value: ColorLike):
        self._below_range_color = Color(value)

    @property
    def return_cpos(self) -> bool:
        """Return or set the default behavior of returning the camera position.

        Examples
        --------
        Disable returning camera position by ``show`` and ``plot`` methods.

        >>> import pyvista as pv
        >>> pv.global_theme.return_cpos = False
        """
        return self._return_cpos

    @return_cpos.setter
    def return_cpos(self, value: bool):
        self._return_cpos = value

    @property
    def background(self) -> Color:
        """Return or set the default background color of pyvista plots.

        Examples
        --------
        Set the default global background of all plots to white.

        >>> import pyvista as pv
        >>> pv.global_theme.background = 'white'
        """
        return self._background

    @background.setter
    def background(self, new_background: ColorLike):
        self._background = Color(new_background)

    @property
    def jupyter_backend(self) -> str:
        """Return or set the jupyter notebook plotting backend.

        Jupyter backend to use when plotting.  Must be one of the
        following:

        * ``'ipyvtklink'`` : DEPRECATED. Render remotely and stream the
          resulting VTK images back to the client.  Supports all VTK
          methods, but suffers from lag due to remote rendering.
          Requires that a virtual framebuffer be set up when displaying
          on a headless server.  Must have ``ipyvtklink`` installed.

        * ``'panel'`` : Convert the VTK render window to a vtkjs
          object and then visualize that within jupyterlab. Supports
          most VTK objects.  Requires that a virtual framebuffer be
          set up when displaying on a headless server.  Must have
          ``panel`` installed.

        * ``'ipygany'`` : Convert all the meshes into ``ipygany``
          meshes and streams those to be rendered on the client side.
          Supports VTK meshes, but few others.  Aside from ``none``,
          this is the only method that does not require a virtual
          framebuffer.  Must have ``ipygany`` installed.

        * ``'pythreejs'`` : Convert all the meshes into ``pythreejs``
          meshes and streams those to be rendered on the client side.
          Aside from ``ipygany``, this is the only method that does
          not require a virtual framebuffer.  Must have ``pythreejs``
          installed.

        * ``'static'`` : Display a single static image within the
          JupyterLab environment.  Still requires that a virtual
          framebuffer be set up when displaying on a headless server,
          but does not require any additional modules to be installed.

        * ``'none'`` : Do not display any plots within jupyterlab,
          instead display using dedicated VTK render windows.  This
          will generate nothing on headless servers even with a
          virtual framebuffer.

        Examples
        --------
        Enable the pythreejs backend.

        >>> import pyvista as pv
        >>> pv.set_jupyter_backend('pythreejs')  # doctest:+SKIP

        Enable the ipygany backend.

        >>> pv.set_jupyter_backend('ipygany')  # doctest:+SKIP

        Enable the panel backend.

        >>> pv.set_jupyter_backend('panel')  # doctest:+SKIP

        Enable the ipyvtklink backend (DEPRECATED).

        >>> pv.set_jupyter_backend('ipyvtklink')  # doctest:+SKIP

        Just show static images.

        >>> pv.set_jupyter_backend('static')  # doctest:+SKIP

        Disable all plotting within JupyterLab and display using a
        standard desktop VTK render window.

        >>> pv.set_jupyter_backend(None)  # doctest:+SKIP

        """
        return self._jupyter_backend

    @jupyter_backend.setter
    def jupyter_backend(self, backend: 'str'):
        from pyvista.jupyter import _validate_jupyter_backend

        self._jupyter_backend = _validate_jupyter_backend(backend)

    @property
    def trame(self) -> _TrameConfig:
        """Return or set the default trame parameters."""
        return self._trame

    @trame.setter
    def trame(self, config: _TrameConfig):
        if not isinstance(config, _TrameConfig):
            raise TypeError('Configuration type must be `_TrameConfig`.')
        self._trame = config

    @property
    def auto_close(self) -> bool:
        """Automatically close the figures when finished plotting.

        .. DANGER::
           Set to ``False`` with extreme caution.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.auto_close = False

        """
        return self._auto_close

    @auto_close.setter
    def auto_close(self, value: bool):
        self._auto_close = value

    @property
    def full_screen(self) -> bool:
        """Return if figures are shown in full screen.

        Examples
        --------
        Set windows to be full screen by default.

        >>> import pyvista as pv
        >>> pv.global_theme.full_screen = True
        """
        return self._full_screen

    @full_screen.setter
    def full_screen(self, value: bool):
        self._full_screen = value

    @property
    def enable_camera_orientation_widget(self) -> bool:
        """Enable the camera orientation widget in all plotters.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.enable_camera_orientation_widget = True
        >>> pv.global_theme.enable_camera_orientation_widget
        True

        """
        return self._enable_camera_orientation_widget

    @enable_camera_orientation_widget.setter
    def enable_camera_orientation_widget(self, value: bool):
        self._enable_camera_orientation_widget = value

    @property
    def camera(self):
        """Return or set the default camera position.

        Examples
        --------
        Set both the position and view of the camera.

        >>> import pyvista as pv
        >>> pv.global_theme.camera = {'position': [1, 1, 1],
        ...                                'viewup': [0, 0, 1]}

        Set the default position of the camera.

        >>> pv.global_theme.camera['position'] = [1, 1, 1]

        Set the default view of the camera.

        >>> pv.global_theme.camera['viewup'] = [0, 0, 1]

        """
        return self._camera

    @camera.setter
    def camera(self, camera):
        if not isinstance(camera, dict):
            raise TypeError(f'Expected ``camera`` to be a dict, not {type(camera).__name__}.')

        if 'position' not in camera:
            raise KeyError('Expected the "position" key in the camera dict.')
        if 'viewup' not in camera:
            raise KeyError('Expected the "viewup" key in the camera dict.')

        self._camera = camera

    @property
    def notebook(self) -> Union[bool, None]:
        """Return or set the state of notebook plotting.

        Setting this to ``True`` always enables notebook plotting,
        while setting it to ``False`` disables plotting even when
        plotting within a jupyter notebook and plots externally.

        Examples
        --------
        Disable all jupyter notebook plotting.

        >>> import pyvista as pv
        >>> pv.global_theme.notebook = False

        """
        return self._notebook

    @notebook.setter
    def notebook(self, value: Union[bool, None]):
        self._notebook = value

    @property
    def window_size(self) -> List[int]:
        """Return or set the default render window size.

        Examples
        --------
        Set window size to ``[400, 400]``.

        >>> import pyvista as pv
        >>> pv.global_theme.window_size = [400, 400]

        """
        return self._window_size

    @window_size.setter
    def window_size(self, window_size: List[int]):
        if len(window_size) != 2:
            raise ValueError('Expected a length 2 iterable for ``window_size``.')

        # ensure positive size
        if window_size[0] < 0 or window_size[1] < 0:
            raise ValueError('Window size must be a positive value.')

        self._window_size = window_size

    @property
    def image_scale(self) -> int:
        """Return or set the default image scale factor."""
        return self._image_scale

    @image_scale.setter
    def image_scale(self, value: int):
        value = int(value)
        if value < 1:
            raise ValueError('Scale factor must be a positive integer.')
        self._image_scale = int(value)

    @property
    def font(self) -> _Font:
        """Return or set the default font size, family, and/or color.

        Examples
        --------
        Set the default font family to 'arial'.  Must be either
        'arial', 'courier', or 'times'.

        >>> import pyvista as pv
        >>> pv.global_theme.font.family = 'arial'

        Set the default font size to 20.

        >>> pv.global_theme.font.size = 20

        Set the default title size to 40.

        >>> pv.global_theme.font.title_size = 40

        Set the default label size to 10.

        >>> pv.global_theme.font.label_size = 10

        Set the default text color to 'grey'.

        >>> pv.global_theme.font.color = 'grey'

        String formatter used to format numerical data to '%.6e'.

        >>> pv.global_theme.font.fmt = '%.6e'

        """
        return self._font

    @font.setter
    def font(self, config: _Font):
        if not isinstance(config, _Font):
            raise TypeError('Configuration type must be `_Font`.')
        self._font = config

    @property
    def cmap(self):
        """Return or set the default colormap of pyvista.

        See available Matplotlib colormaps.  Only applicable for when
        displaying ``scalars``. Requires Matplotlib to be installed.
        If ``colorcet`` or ``cmocean`` are installed, their colormaps
        can be specified by name.

        You can also specify a list of colors to override an existing
        colormap with a custom one.  For example, to create a three
        color colormap you might specify ``['green', 'red', 'blue']``

        Examples
        --------
        Set the default global colormap to 'jet'.

        >>> import pyvista as pv
        >>> pv.global_theme.cmap = 'jet'

        """
        return self._cmap

    @cmap.setter
    def cmap(self, cmap):
        try:
            get_cmap_safe(cmap)  # for validation
            self._cmap = cmap
        except ImportError:  # pragma: no cover
            warnings.warn(
                'Unable to set a default theme colormap without matplotlib. '
                'The builtin VTK "jet" colormap will be used.'
            )
            self._cmap = None

    @property
    def color(self) -> Color:
        """Return or set the default color of meshes in pyvista.

        Used for meshes without ``scalars``.

        When setting, the value must be either a string, rgb list,
        or hex color string.  For example:

        * ``color='white'``
        * ``color='w'``
        * ``color=[1.0, 1.0, 1.0]``
        * ``color='#FFFFFF'``

        Examples
        --------
        Set the default mesh color to 'red'.

        >>> import pyvista as pv
        >>> pv.global_theme.color = 'red'

        """
        return self._color

    @color.setter
    def color(self, color: ColorLike):
        self._color = Color(color)

    @property
    def color_cycler(self):
        """Return or set the default color cycler used to color meshes.

        This color cycler is iterated over by each renderer to sequentially
        color datasets when displaying them through ``add_mesh``.

        When setting, the value must be either a list of color-like objects,
        or a cycler of color-like objects. If the value passed is a single
        string, it must be one of:

            * ``'default'`` - Use the default color cycler (matches matplotlib's default)
            * ``'matplotlib`` - Dynamically get matplotlib's current theme's color cycler.
            * ``'all'`` - Cycle through all of the available colors in ``pyvista.plotting.colors.hexcolors``

        Setting to ``None`` will disable the use of the color cycler.

        Examples
        --------
        Set the default color cycler to iterate through red, green, and blue.

        >>> import pyvista as pv
        >>> pv.global_theme.color_cycler = ['red', 'green', 'blue']

        >>> pl = pv.Plotter()
        >>> _ = pl.add_mesh(pv.Cone(center=(0, 0, 0)))      # red
        >>> _ = pl.add_mesh(pv.Cube(center=(1, 0, 0)))      # green
        >>> _ = pl.add_mesh(pv.Sphere(center=(1, 1, 0)))    # blue
        >>> _ = pl.add_mesh(pv.Cylinder(center=(0, 1, 0)))  # red again
        >>> pl.show()  # doctest: +SKIP

        """
        return self._color_cycler

    @color_cycler.setter
    def color_cycler(self, color_cycler):
        self._color_cycler = get_cycler(color_cycler)

    @property
    def nan_color(self) -> Color:
        """Return or set the default NaN color.

        This color is used to plot all NaN values.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.nan_color = 'darkgray'

        """
        return self._nan_color

    @nan_color.setter
    def nan_color(self, nan_color: ColorLike):
        self._nan_color = Color(nan_color)

    @property
    def edge_color(self) -> Color:
        """Return or set the default edge color.

        Examples
        --------
        Set the global edge color to 'blue'.

        >>> import pyvista as pv
        >>> pv.global_theme.edge_color = 'blue'

        """
        return self._edge_color

    @edge_color.setter
    def edge_color(self, edge_color: ColorLike):
        self._edge_color = Color(edge_color)

    @property
    def line_width(self) -> float:
        """Return or set the default line width.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.line_width = 2.0

        """
        return self._line_width

    @line_width.setter
    def line_width(self, line_width: float):
        self._line_width = float(line_width)

    @property
    def point_size(self) -> float:
        """Return or set the default point size.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.line_width = 10.0

        """
        return self._point_size

    @point_size.setter
    def point_size(self, point_size: float):
        self._point_size = float(point_size)

    @property
    def outline_color(self) -> Color:
        """Return or set the default outline color.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.outline_color = 'white'

        """
        return self._outline_color

    @outline_color.setter
    def outline_color(self, outline_color: ColorLike):
        self._outline_color = Color(outline_color)

    @property
    def floor_color(self) -> Color:
        """Return or set the default floor color.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.floor_color = 'black'

        """
        return self._floor_color

    @floor_color.setter
    def floor_color(self, floor_color: ColorLike):
        self._floor_color = Color(floor_color)

    @property
    def colorbar_orientation(self) -> str:
        """Return or set the default colorbar orientation.

        Must be either ``'vertical'`` or ``'horizontal'``.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.colorbar_orientation = 'horizontal'

        """
        return self._colorbar_orientation

    @colorbar_orientation.setter
    def colorbar_orientation(self, colorbar_orientation: str):
        if colorbar_orientation not in ['vertical', 'horizontal']:
            raise ValueError('Colorbar orientation must be either "vertical" or "horizontal"')
        self._colorbar_orientation = colorbar_orientation

    @property
    def colorbar_horizontal(self) -> _ColorbarConfig:
        """Return or set the default parameters of a horizontal colorbar.

        Examples
        --------
        Set the default horizontal colorbar width to 0.6.

        >>> import pyvista as pv
        >>> pv.global_theme.colorbar_horizontal.width = 0.6

        Set the default horizontal colorbar height to 0.2.

        >>> pv.global_theme.colorbar_horizontal.height = 0.2

        """
        return self._colorbar_horizontal

    @colorbar_horizontal.setter
    def colorbar_horizontal(self, config: _ColorbarConfig):
        if not isinstance(config, _ColorbarConfig):
            raise TypeError('Configuration type must be `_ColorbarConfig`.')
        self._colorbar_horizontal = config

    @property
    def colorbar_vertical(self) -> _ColorbarConfig:
        """Return or set the default parameters of a vertical colorbar.

        Examples
        --------
        Set the default colorbar width to 0.45.

        >>> import pyvista as pv
        >>> pv.global_theme.colorbar_vertical.width = 0.45

        Set the default colorbar height to 0.8.

        >>> import pyvista as pv
        >>> pv.global_theme.colorbar_vertical.height = 0.8

        """
        return self._colorbar_vertical

    @colorbar_vertical.setter
    def colorbar_vertical(self, config: _ColorbarConfig):
        if not isinstance(config, _ColorbarConfig):
            raise TypeError('Configuration type must be `_ColorbarConfig`.')
        self._colorbar_vertical = config

    @property
    def show_scalar_bar(self) -> bool:
        """Return or set the default color bar visibility.

        Examples
        --------
        Show the scalar bar by default when scalars are available.

        >>> import pyvista as pv
        >>> pv.global_theme.show_scalar_bar = True

        """
        return self._show_scalar_bar

    @show_scalar_bar.setter
    def show_scalar_bar(self, show_scalar_bar: bool):
        self._show_scalar_bar = bool(show_scalar_bar)

    @property
    def show_edges(self) -> bool:
        """Return or set the default edge visibility.

        Examples
        --------
        Show edges globally by default.

        >>> import pyvista as pv
        >>> pv.global_theme.show_edges = True

        """
        return self._show_edges

    @show_edges.setter
    def show_edges(self, show_edges: bool):
        self._show_edges = bool(show_edges)

    @property
    def show_vertices(self) -> bool:
        """Return or set the default vertex visibility.

        Examples
        --------
        Show vertices globally by default.

        >>> import pyvista as pv
        >>> pv.global_theme.show_vertices = True

        """
        return self._show_vertices

    @show_vertices.setter
    def show_vertices(self, show_vertices: bool):
        self._show_vertices = bool(show_vertices)

    @property
    def lighting(self) -> bool:
        """Return or set the default ``lighting``.

        Examples
        --------
        Disable lighting globally.

        >>> import pyvista as pv
        >>> pv.global_theme.lighting = False
        """
        return self._lighting

    @lighting.setter
    def lighting(self, lighting: bool):
        self._lighting = lighting

    @property
    def interactive(self) -> bool:
        """Return or set the default ``interactive`` parameter.

        Examples
        --------
        Make all plots non-interactive globally.

        >>> import pyvista as pv
        >>> pv.global_theme.interactive = False
        """
        return self._interactive

    @interactive.setter
    def interactive(self, interactive: bool):
        self._interactive = bool(interactive)

    @property
    def render_points_as_spheres(self) -> bool:
        """Return or set the default ``render_points_as_spheres`` parameter.

        Examples
        --------
        Render points as spheres by default globally.

        >>> import pyvista as pv
        >>> pv.global_theme.render_points_as_spheres = True
        """
        return self._render_points_as_spheres

    @render_points_as_spheres.setter
    def render_points_as_spheres(self, render_points_as_spheres: bool):
        self._render_points_as_spheres = bool(render_points_as_spheres)

    @property
    def render_lines_as_tubes(self) -> bool:
        """Return or set the default ``render_lines_as_tubes`` parameter.

        Examples
        --------
        Render points as spheres by default globally.

        >>> import pyvista as pv
        >>> pv.global_theme.render_lines_as_tubes = True
        """
        return self._render_lines_as_tubes

    @render_lines_as_tubes.setter
    def render_lines_as_tubes(self, render_lines_as_tubes: bool):
        self._render_lines_as_tubes = bool(render_lines_as_tubes)

    @property
    def transparent_background(self) -> bool:
        """Return or set the default ``transparent_background`` parameter.

        Examples
        --------
        Set transparent_background globally to ``True``.

        >>> import pyvista as pv
        >>> pv.global_theme.transparent_background = True

        """
        return self._transparent_background

    @transparent_background.setter
    def transparent_background(self, transparent_background: bool):
        self._transparent_background = transparent_background

    @property
    def title(self) -> str:
        """Return or set the default ``title`` parameter.

        This is the VTK render window title.

        Examples
        --------
        Set title globally to 'plot'.

        >>> import pyvista as pv
        >>> pv.global_theme.title = 'plot'

        """
        return self._title

    @title.setter
    def title(self, title: str):
        self._title = title

    @property
    def anti_aliasing(self) -> Optional[str]:
        """Enable or disable anti-aliasing.

        Should be either ``"ssaa"``, ``"msaa"``, ``"fxaa"``, or ``None``.

        Examples
        --------
        Use super-sampling anti-aliasing in the global theme.

        >>> import pyvista as pv
        >>> pv.global_theme.anti_aliasing = 'ssaa'
        >>> pv.global_theme.anti_aliasing
        'ssaa'

        Disable anti-aliasing in the global theme.

        >>> import pyvista as pv
        >>> pv.global_theme.anti_aliasing = None

        See :ref:`anti_aliasing_example` for more information regarding
        anti-aliasing.

        """
        return self._anti_aliasing

    @anti_aliasing.setter
    def anti_aliasing(self, anti_aliasing: Union[str, None]):
        if isinstance(anti_aliasing, bool):
            # Deprecated on v0.37.0, estimated removal on v0.40.0
            warnings.warn(
                '`anti_aliasing` is now a string or None and must be either "ssaa", '
                '"msaa", "fxaa", or None',
                PyVistaDeprecationWarning,
            )
            anti_aliasing = 'fxaa' if anti_aliasing else None

        if isinstance(anti_aliasing, str):
            if anti_aliasing not in ['ssaa', 'msaa', 'fxaa']:
                raise ValueError('anti_aliasing must be either "ssaa", "msaa", or "fxaa"')
        elif anti_aliasing is not None:
            raise TypeError('anti_aliasing must be either "ssaa", "msaa", "fxaa", or None')

        self._anti_aliasing = anti_aliasing

    @property
    def antialiasing(self):
        """Enable or disable anti-aliasing.

        .. deprecated:: 0.37.0
           Deprecated in favor of :attr:`anti_aliasing <DefaultTheme.anti_aliasing>`.
        """
        # Recommended removing at pyvista==0.40.0
        warnings.warn(
            'antialising is deprecated.  Please use `anti_aliasing` instead.',
            PyVistaDeprecationWarning,
        )
        return self.anti_aliasing

    @antialiasing.setter
    def antialiasing(self, value):  # pragma: no cover
        # Recommended removing at pyvista==0.40.0
        warnings.warn(
            'antialising is deprecated.  Please use `anti_aliasing` instead.',
            PyVistaDeprecationWarning,
        )
        self.anti_aliasing = value

    @property
    def multi_samples(self) -> int:
        """Return or set the default ``multi_samples`` parameter.

        Set the number of multisamples to used with hardware anti_aliasing. This
        is only used when :attr:`anti_aliasing <DefaultTheme.anti_aliasing>` is
        set to ``"msaa"``.

        Examples
        --------
        Set the default number of multisamples to 2 and enable ``"msaa"``

        >>> import pyvista as pv
        >>> pv.global_theme.anti_aliasing = 'msaa'
        >>> pv.global_theme.multi_samples = 2

        """
        return self._multi_samples

    @multi_samples.setter
    def multi_samples(self, multi_samples: int):
        self._multi_samples = int(multi_samples)

    @property
    def multi_rendering_splitting_position(self) -> float:
        """Return or set the default ``multi_rendering_splitting_position`` parameter.

        Examples
        --------
        Set multi_rendering_splitting_position globally to 0.5 (the
        middle of the window).

        >>> import pyvista as pv
        >>> pv.global_theme.multi_rendering_splitting_position = 0.5

        """
        return self._multi_rendering_splitting_position

    @multi_rendering_splitting_position.setter
    def multi_rendering_splitting_position(self, multi_rendering_splitting_position: float):
        self._multi_rendering_splitting_position = multi_rendering_splitting_position

    @property
    def volume_mapper(self) -> str:
        """Return or set the default ``volume_mapper`` parameter.

        Must be one of the following strings, which are mapped to the
        following VTK volume mappers.

        * ``'fixed_point'`` : ``vtk.vtkFixedPointVolumeRayCastMapper``
        * ``'gpu'`` : ``vtk.vtkGPUVolumeRayCastMapper``
        * ``'open_gl'`` : ``vtk.vtkOpenGLGPUVolumeRayCastMapper``
        * ``'smart'`` : ``vtk.vtkSmartVolumeMapper``

        Examples
        --------
        Set default volume mapper globally to 'gpu'.

        >>> import pyvista as pv
        >>> pv.global_theme.volume_mapper = 'gpu'

        """
        return self._volume_mapper

    @volume_mapper.setter
    def volume_mapper(self, mapper: str):
        mappers = ['fixed_point', 'gpu', 'open_gl', 'smart']
        if mapper not in mappers:
            raise ValueError(
                f"Mapper ({mapper}) unknown. Available volume mappers "
                f"include:\n {', '.join(mappers)}"
            )

        self._volume_mapper = mapper

    @property
    def smooth_shading(self) -> bool:
        """Return or set the default ``smooth_shading`` parameter.

        Examples
        --------
        Set the global smooth_shading parameter default to ``True``.

        >>> import pyvista as pv
        >>> pv.global_theme.smooth_shading = True

        """
        return self._smooth_shading

    @smooth_shading.setter
    def smooth_shading(self, smooth_shading: bool):
        self._smooth_shading = bool(smooth_shading)

    @property
    def depth_peeling(self) -> _DepthPeelingConfig:
        """Return or set the default depth peeling parameters.

        Examples
        --------
        Set the global depth_peeling parameter default to be enabled
        with 8 peels.

        >>> import pyvista as pv
        >>> pv.global_theme.depth_peeling.number_of_peels = 8
        >>> pv.global_theme.depth_peeling.occlusion_ratio = 0.0
        >>> pv.global_theme.depth_peeling.enabled = True

        """
        return self._depth_peeling

    @depth_peeling.setter
    def depth_peeling(self, config: _DepthPeelingConfig):
        if not isinstance(config, _DepthPeelingConfig):
            raise TypeError('Configuration type must be `_DepthPeelingConfig`.')
        self._depth_peeling = config

    @property
    def silhouette(self) -> _SilhouetteConfig:
        """Return or set the default ``silhouette`` configuration.

        Examples
        --------
        Set parameters of the silhouette.

        >>> import pyvista as pv
        >>> pv.global_theme.silhouette.color = 'grey'
        >>> pv.global_theme.silhouette.line_width = 2.0
        >>> pv.global_theme.silhouette.feature_angle = 20

        """
        return self._silhouette

    @silhouette.setter
    def silhouette(self, config: _SilhouetteConfig):
        if not isinstance(config, _SilhouetteConfig):
            raise TypeError('Configuration type must be `_SilhouetteConfig`')
        self._silhouette = config

    @property
    def slider_styles(self) -> _SliderConfig:
        """Return the default slider style configurations."""
        return self._slider_styles

    @slider_styles.setter
    def slider_styles(self, config: _SliderConfig):
        if not isinstance(config, _SliderConfig):
            raise TypeError('Configuration type must be `_SliderConfig`.')
        self._slider_styles = config

    @property
    def axes(self) -> _AxesConfig:
        """Return or set the default ``axes`` configuration.

        Examples
        --------
        Set the x axis color to black.

        >>> import pyvista as pv
        >>> pv.global_theme.axes.x_color = 'black'

        Show axes by default.

        >>> pv.global_theme.axes.show = True

        Use the ``vtk.vtkCubeAxesActor``.

        >>> pv.global_theme.axes.box = True

        """
        return self._axes

    @axes.setter
    def axes(self, config: _AxesConfig):
        if not isinstance(config, _AxesConfig):
            raise TypeError('Configuration type must be `_AxesConfig`.')
        self._axes = config

    @property
    def before_close_callback(self) -> Callable[[Plotter], None]:
        """Return the default before_close_callback function for Plotter."""
        return self._before_close_callback

    @before_close_callback.setter
    def before_close_callback(self, value: Callable[[Plotter], None]):
        self._before_close_callback = value

    def restore_defaults(self):
        """Restore the theme defaults.

        Examples
        --------
        >>> import pyvista as pv
        >>> pv.global_theme.restore_defaults()

        """
        self.__init__()

    def __repr__(self):
        """User friendly representation of the current theme."""
        txt = [f'{self.name.capitalize()} Theme']
        txt.append('-' * len(txt[0]))
        parm = {
            'Background': 'background',
            'Jupyter backend': 'jupyter_backend',
            'Full screen': 'full_screen',
            'Window size': 'window_size',
            'Camera': 'camera',
            'Notebook': 'notebook',
            'Font': 'font',
            'Auto close': 'auto_close',
            'Colormap': 'cmap',
            'Color': 'color',
            'Color Cycler': 'color_cycler',
            'NaN color': 'nan_color',
            'Edge color': 'edge_color',
            'Outline color': 'outline_color',
            'Floor color': 'floor_color',
            'Colorbar orientation': 'colorbar_orientation',
            'Colorbar - horizontal': 'colorbar_horizontal',
            'Colorbar - vertical': 'colorbar_vertical',
            'Show scalar bar': 'show_scalar_bar',
            'Show edges': 'show_edges',
            'Lighting': 'lighting',
            'Interactive': 'interactive',
            'Render points as spheres': 'render_points_as_spheres',
            'Transparent Background': 'transparent_background',
            'Title': 'title',
            'Axes': 'axes',
            'Multi-samples': 'multi_samples',
            'Multi-renderer Split Pos': 'multi_rendering_splitting_position',
            'Volume mapper': 'volume_mapper',
            'Smooth shading': 'smooth_shading',
            'Depth peeling': 'depth_peeling',
            'Silhouette': 'silhouette',
            'Slider Styles': 'slider_styles',
            'Return Camera Position': 'return_cpos',
            'Hidden Line Removal': 'hidden_line_removal',
            'Anti-Aliasing': '_anti_aliasing',
            'Split sharp edges': '_split_sharp_edges',
            'Sharp edges feat. angle': '_sharp_edges_feature_angle',
            'Before close callback': '_before_close_callback',
        }
        for name, attr in parm.items():
            setting = getattr(self, attr)
            txt.append(f'{name:<25}: {setting}')

        return '\n'.join(txt)

    @property
    def name(self) -> str:
        """Return or set the name of the theme."""
        return self._name

    @name.setter
    def name(self, name: str):
        self._name = name

    def load_theme(self, theme):
        """Overwrite the current theme with a theme.

        Parameters
        ----------
        theme : pyvista.themes.DefaultTheme
            Theme to use to overwrite this theme.

        Examples
        --------
        Create a custom theme from the default theme and load it into
        the global theme of pyvista.

        >>> import pyvista as pv
        >>> from pyvista.themes import DefaultTheme
        >>> my_theme = DefaultTheme()
        >>> my_theme.font.size = 20
        >>> my_theme.font.title_size = 40
        >>> my_theme.cmap = 'jet'
        ...
        >>> pv.global_theme.load_theme(my_theme)
        >>> pv.global_theme.font.size
        20

        Create a custom theme from the dark theme and load it into
        pyvista.

        >>> from pyvista.themes import DarkTheme
        >>> my_theme = DarkTheme()
        >>> my_theme.show_edges = True
        >>> pv.global_theme.load_theme(my_theme)
        >>> pv.global_theme.show_edges
        True

        """
        if isinstance(theme, str):
            theme = load_theme(theme)

        if not isinstance(theme, DefaultTheme):
            raise TypeError(
                '``theme`` must be a pyvista theme like ``pyvista.themes.DefaultTheme``.'
            )

        for attr_name in theme.__slots__:
            setattr(self, attr_name, getattr(theme, attr_name))

    def save(self, filename):
        """Serialize this theme to a json file.

        ``before_close_callback`` is non-serializable and is omitted.

        Parameters
        ----------
        filename : str
            Path to save the theme to.  Should end in ``'.json'``.

        Examples
        --------
        Export and then load back in a theme.

        >>> import pyvista as pv
        >>> theme = pv.themes.DefaultTheme()
        >>> theme.background = 'white'
        >>> theme.save('my_theme.json')  # doctest:+SKIP
        >>> loaded_theme = pv.load_theme('my_theme.json')  # doctest:+SKIP

        """
        data = self.to_dict()
        # functions are not serializable
        del data["before_close_callback"]
        with open(filename, 'w') as f:
            json.dump(data, f)

    @property
    def split_sharp_edges(self) -> bool:
        """Set or return splitting sharp edges.

        See :ref:`shading_example` for an example showing split sharp edges.

        Examples
        --------
        Enable the splitting of sharp edges globally.

        >>> import pyvista as pv
        >>> pv.global_theme.split_sharp_edges = True
        >>> pv.global_theme.split_sharp_edges
        True

        Disable the splitting of sharp edges globally.

        >>> import pyvista as pv
        >>> pv.global_theme.split_sharp_edges = False
        >>> pv.global_theme.split_sharp_edges
        False

        """
        return self._split_sharp_edges

    @split_sharp_edges.setter
    def split_sharp_edges(self, value: bool):
        self._split_sharp_edges = value

    @property
    def sharp_edges_feature_angle(self) -> float:
        """Set or return the angle of the sharp edges feature angle.

        See :ref:`shading_example` for an example showing split sharp edges.

        Examples
        --------
        Change the sharp edges feature angle to 45 degrees.

        >>> import pyvista as pv
        >>> pv.global_theme.sharp_edges_feature_angle = 45.0
        >>> pv.global_theme.sharp_edges_feature_angle
        45.0

        """
        return self._sharp_edges_feature_angle

    @sharp_edges_feature_angle.setter
    def sharp_edges_feature_angle(self, value: float):
        self._sharp_edges_feature_angle = float(value)

    @property
    def lighting_params(self) -> _LightingConfig:
        """Return or set the default lighting configuration."""
        return self._lighting_params

    @lighting_params.setter
    def lighting_params(self, config: _LightingConfig):
        if not isinstance(config, _LightingConfig):
            raise TypeError('Configuration type must be `_LightingConfig`.')
        self._lighting_params = config


class DarkTheme(DefaultTheme):
    """Dark mode theme.

    Black background, "viridis" colormap, tan meshes, white (hidden) edges.

    Examples
    --------
    Make the dark theme the global default.

    >>> import pyvista as pv
    >>> from pyvista import themes
    >>> pv.set_plot_theme(themes.DarkTheme())

    Alternatively, set via a string.

    >>> pv.set_plot_theme('dark')

    """

    def __init__(self):
        """Initialize the theme."""
        super().__init__()
        self.name = 'dark'
        self.background = 'black'
        self.cmap = 'viridis'
        self.font.color = 'white'
        self.show_edges = False
        self.color = 'tan'
        self.outline_color = 'white'
        self.edge_color = 'white'
        self.axes.x_color = 'tomato'
        self.axes.y_color = 'seagreen'
        self.axes.z_color = 'blue'


class ParaViewTheme(DefaultTheme):
    """A paraview-like theme.

    Examples
    --------
    Make the paraview-like theme the global default.

    >>> import pyvista as pv
    >>> from pyvista import themes
    >>> pv.set_plot_theme(themes.ParaViewTheme())

    Alternatively, set via a string.

    >>> pv.set_plot_theme('paraview')

    """

    def __init__(self):
        """Initialize theme."""
        super().__init__()
        self.name = 'paraview'
        self.background = 'paraview'
        self.cmap = 'coolwarm'
        self.font.family = 'arial'
        self.font.label_size = 16
        self.font.color = 'white'
        self.show_edges = False
        self.color = 'white'
        self.outline_color = 'white'
        self.edge_color = 'black'
        self.axes.x_color = 'tomato'
        self.axes.y_color = 'gold'
        self.axes.z_color = 'green'


class DocumentTheme(DefaultTheme):
    """A document theme well suited for papers and presentations.

    This theme uses:

    * A white background
    * Black fonts
    * The "viridis" colormap
    * disables edges for surface plots
    * Hidden edge removal

    Best used for presentations, papers, etc.

    Examples
    --------
    Make the document theme the global default.

    >>> import pyvista as pv
    >>> from pyvista import themes
    >>> pv.set_plot_theme(themes.DocumentTheme())

    Alternatively, set via a string.

    >>> pv.set_plot_theme('document')

    """

    def __init__(self):
        """Initialize the theme."""
        super().__init__()
        self.name = 'document'
        self.background = 'white'
        self.cmap = 'viridis'
        self.font.size = 18
        self.font.title_size = 18
        self.font.label_size = 18
        self.font.color = 'black'
        self.show_edges = False
        self.color = 'tan'
        self.outline_color = 'black'
        self.edge_color = 'black'
        self.axes.x_color = 'tomato'
        self.axes.y_color = 'seagreen'
        self.axes.z_color = 'blue'


class DocumentProTheme(DocumentTheme):
    """A more professional document theme.

    This theme extends the base document theme with:

    * Default color cycling
    * Rendering points as spheres
    * MSAA anti aliassing
    * Depth peeling

    """

    def __init__(self):
        """Initialize the theme."""
        super().__init__()
        self.color_cycler = get_cycler('default')
        self.render_points_as_spheres = True
        self.anti_aliasing = 'msaa'  # or 'ssaa'?
        self.multi_samples = 2
        self.depth_peeling.number_of_peels = 4
        self.depth_peeling.occlusion_ratio = 0.0
        self.depth_peeling.enabled = True


class _TestingTheme(DefaultTheme):
    """Low resolution testing theme for ``pytest``.

    Necessary for image regression.  Xvfb doesn't support
    multi-sampling, it's disabled for consistency between desktops and
    remote testing.

    Also disables ``return_cpos`` to make it easier for us to write
    examples without returning camera positions.

    """

    def __init__(self):
        super().__init__()
        self.name = 'testing'
        self.multi_samples = 1
        self.window_size = [400, 400]
        self.axes.show = False
        self.return_cpos = False


class _NATIVE_THEMES(Enum):
    """Global built-in themes available to PyVista."""

    paraview = ParaViewTheme
    document = DocumentTheme
    document_pro = DocumentProTheme
    dark = DarkTheme
    default = DefaultTheme
    testing = _TestingTheme
