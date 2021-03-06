import numpy as np
import itertools as it

from helpers import *

from mobject import Mobject
from mobject.vectorized_mobject import VMobject
from mobject.tex_mobject import TextMobject
from animation import Animation


class Rotating(Animation):
    CONFIG = {
        "axes"       : [],
        "axis"       : OUT,
        "radians"    : 2*np.pi,
        "run_time"   : 5,
        "rate_func"  : None,
        "in_place"   : True,
        "about_point" : None,
    }
    def update_submobject(self, submobject, starting_submobject, alpha):
        submobject.points = np.array(starting_submobject.points)

    def update_mobject(self, alpha):
        Animation.update_mobject(self, alpha)
        axes = self.axes if self.axes else [self.axis]
        about_point = None
        if self.about_point is not None:
            about_point = self.about_point
        elif self.in_place: #This is superseeded
            self.about_point = self.mobject.get_center()
        self.mobject.rotate(
            alpha*self.radians, 
            axes = axes,
            about_point = self.about_point
        )


class ShowPartial(Animation):
    def update_submobject(self, submobject, starting_submobject, alpha):
        submobject.pointwise_become_partial(
            starting_submobject, *self.get_bounds(alpha)
        )

    def get_bounds(self, alpha):
        raise Exception("Not Implemented")


class ShowCreation(ShowPartial):
    CONFIG = {
        "submobject_mode" : "one_at_a_time",
    }
    def get_bounds(self, alpha):
        return (0, alpha)

class Uncreate(ShowCreation):
    CONFIG = {
        "rate_func" : lambda t : smooth(1-t),
        "remover"   : True
    }

class Write(ShowCreation):
    CONFIG = {
        "rate_func" : None,
        "submobject_mode" : "lagged_start",
    }
    def __init__(self, mob_or_text, **kwargs):
        digest_config(self, kwargs)        
        if isinstance(mob_or_text, str):
            mobject = TextMobject(mob_or_text)
        else:
            mobject = mob_or_text
        if "run_time" not in kwargs:
            self.establish_run_time(mobject)
        if "lag_factor" not in kwargs:
            self.lag_factor = max(self.run_time - 1, 2)
        ShowCreation.__init__(self, mobject, **kwargs)

    def establish_run_time(self, mobject):
        num_subs = len(mobject.family_members_with_points())
        if num_subs < 5:
            self.run_time = 1
        elif num_subs < 15:
            self.run_time = 2
        else:
            self.run_time = 3


class ShowPassingFlash(ShowPartial):
    CONFIG = {
        "time_width" : 0.1
    }
    def get_bounds(self, alpha):
        alpha *= (1+self.time_width)
        alpha -= self.time_width/2
        lower = max(0, alpha - self.time_width/2)
        upper = min(1, alpha + self.time_width/2)
        return (lower, upper)


class MoveAlongPath(Animation):
    def __init__(self, mobject, vmobject, **kwargs):
        digest_config(self, kwargs, locals())
        Animation.__init__(self, mobject, **kwargs)

    def update_mobject(self, alpha):
        self.mobject.shift(
            self.vmobject.point_from_proportion(alpha) - \
            self.mobject.get_center()
        )

class Homotopy(Animation):
    CONFIG = {
        "run_time" : 3,
        "apply_function_kwargs" : {},
    }
    def __init__(self, homotopy, mobject, **kwargs):
        """
        Homotopy a function from (x, y, z, t) to (x', y', z')
        """
        def function_at_time_t(t):
            return lambda p : homotopy(p[0], p[1], p[2], t)
        self.function_at_time_t = function_at_time_t
        digest_config(self, kwargs)
        Animation.__init__(self, mobject, **kwargs)

    def update_submobject(self, submob, start, alpha):
        submob.points = start.points
        submob.apply_function(
            self.function_at_time_t(alpha),
            **self.apply_function_kwargs
        )

class SmoothedVectorizedHomotopy(Homotopy):
    def update_submobject(self, submob, start, alpha):
        Homotopy.update_submobject(self, submob, start, alpha)
        submob.make_smooth()


class PhaseFlow(Animation):
    CONFIG = {
        "virtual_time" : 1,
        "rate_func" : None,
    }
    def __init__(self, function, mobject, **kwargs):
        digest_config(self, kwargs, locals())        
        Animation.__init__(self, mobject, **kwargs)

    def update_mobject(self, alpha):
        if hasattr(self, "last_alpha"):
            dt = self.virtual_time*(alpha-self.last_alpha)
            self.mobject.apply_function(
                lambda p : p + dt*self.function(p)
            )
        self.last_alpha = alpha

class MoveAlongPath(Animation):
    def __init__(self, mobject, path, **kwargs):
        digest_config(self, kwargs, locals())
        Animation.__init__(self, mobject, **kwargs)

    def update_mobject(self, alpha):
        point = self.path.point_from_proportion(alpha)
        self.mobject.move_to(point)

class UpdateFromFunc(Animation):
    """
    update_function of the form func(mobject), presumably
    to be used when the state of one mobject is dependent
    on another simultaneously animated mobject
    """
    def __init__(self, mobject, update_function, **kwargs):
        digest_config(self, kwargs, locals())
        Animation.__init__(self, mobject, **kwargs)

    def update_mobject(self, alpha):
        self.update_function(self.mobject)

class UpdateFromAlphaFunc(UpdateFromFunc):
    def update_mobject(self, alpha):
        self.update_function(self.mobject, alpha)
        

class MaintainPositionRelativeTo(Animation):
    CONFIG = {
        "tracked_critical_point" : ORIGIN
    }
    def __init__(self, mobject, tracked_mobject, **kwargs):
        digest_config(self, kwargs, locals())
        tcp = self.tracked_critical_point
        self.diff = mobject.get_critical_point(tcp) - \
                    tracked_mobject.get_critical_point(tcp)
        Animation.__init__(self, mobject, **kwargs)

    def update_mobject(self, alpha):
        self.mobject.shift(
            self.tracked_mobject.get_critical_point(self.tracked_critical_point) - \
            self.mobject.get_critical_point(self.tracked_critical_point) + \
            self.diff
        )


### Animation modifiers ###

class ApplyToCenters(Animation):
    def __init__(self, AnimationClass, mobjects, **kwargs):
        full_kwargs = AnimationClass.CONFIG
        full_kwargs.update(kwargs)
        full_kwargs["mobject"] = Mobject(*[
            mob.get_point_mobject()
            for mob in mobjects
        ])
        self.centers_container = AnimationClass(**full_kwargs)
        full_kwargs.pop("mobject")
        Animation.__init__(self, Mobject(*mobjects), **full_kwargs)
        self.name = str(self) + AnimationClass.__name__

    def update_mobject(self, alpha):
        self.centers_container.update_mobject(alpha)
        center_mobs = self.centers_container.mobject.split()
        mobjects = self.mobject.split()        
        for center_mob, mobject in zip(center_mobs, mobjects):
            mobject.shift(
                center_mob.get_center()-mobject.get_center()
            )



class DelayByOrder(Animation):
    """
    Modifier of animation.

    Warning: This will not work on all animation types.
    """
    CONFIG = {
        "max_power" : 5
    }
    def __init__(self, animation, **kwargs):
        digest_locals(self)
        self.num_mobject_points = animation.mobject.get_num_points()        
        kwargs.update(dict([
            (attr, getattr(animation, attr))
            for attr in Animation.CONFIG
        ]))
        Animation.__init__(self, animation.mobject, **kwargs)
        self.name = str(self) + str(self.animation)

    def update_mobject(self, alpha):
        dim = self.mobject.DIM
        alpha_array = np.array([
            [alpha**power]*dim
            for n in range(self.num_mobject_points)
            for prop in [(n+1.0)/self.num_mobject_points]
            for power in [1+prop*(self.max_power-1)]
        ])
        self.animation.update_mobject(alpha_array)


class Succession(Animation):
    def __init__(self, *animations, **kwargs):
        if "run_time" in kwargs:
            run_time = kwargs.pop("run_time")
        else:
            run_time = sum([anim.run_time for anim in animations])
        self.num_anims = len(animations)
        self.anims = (animations)
        mobject = Mobject(*[anim.mobject for anim in self.anims])
        self.last_index = 0
        Animation.__init__(self, mobject, run_time = run_time, **kwargs)

    def update_mobject(self, alpha):
        scaled_alpha = alpha*self.num_anims
        index = min(int(scaled_alpha), len(self.anims)-1)
        curr_anim = self.anims[index]
        if index != self.last_index:
            last_anim = self.anims[self.last_index]
            last_anim.clean_up()
            if last_anim.mobject is curr_anim.mobject:
                #TODO, is there a way to do this that doesn't
                #require leveraging implementation details of 
                #Animations, and knowing about the different
                #struction of Transform?
                if hasattr(curr_anim, "ending_mobject"):
                    curr_anim.mobject.align_data(curr_anim.ending_mobject)
                curr_anim.starting_mobject = curr_anim.mobject.copy()
        curr_anim.update(scaled_alpha - index)
        self.last_index = index

class AnimationGroup(Animation):
    def __init__(self, *sub_anims, **kwargs):
        digest_config(self, kwargs, locals())
        max_run_time = float(max([a.run_time for a in sub_anims]))
        for anim in sub_anims:
            #Use np.divide to that 1./0 = np.inf
            anim.alpha_multiplier = np.divide(max_run_time, anim.run_time)

        if "run_time" in kwargs:
            self.run_time = kwargs.pop("run_time")
        else:
            self.run_time = max_run_time
        everything = Mobject(*[a.mobject for a in sub_anims])
        Animation.__init__(self, everything, **kwargs)

    def update(self, alpha):
        for anim in self.sub_anims:
            sub_alpha = np.clip(alpha*anim.alpha_multiplier, 0, 1)
            anim.update(sub_alpha)





















