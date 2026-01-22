# This file exists solely as a Phase 1 validation artifact and is not part of
# the runtime engine.

from .scene_generator import generate_scene
from .scene_generator_contrast import generate_scene as generate_contrasting_scene

if __name__ == "__main__":
    scene_one = generate_scene()
    scene_two = generate_contrasting_scene()

    separator = "\n\n" + "="*80 + "\n\n"

    print(scene_one + separator + scene_two)
