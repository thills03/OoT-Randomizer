.n64
.relativeinclude on

.create "../roms/patched.z64", 0
.incbin "../roms/base.z64"
.include "macros.asm"

;==================================================================================================
; Constants
;==================================================================================================

.include "constants.asm"
.include "addresses.asm"

;==================================================================================================
; Base game editing region
;==================================================================================================

.include "boot.asm"
.include "hacks.asm"
.include "malon.asm"
.include "mido.asm"

;==================================================================================================
; New code region
;==================================================================================================

.headersize (0x80400000 - 0x03480000)

.org 0x80400000
.area 0x20000 //payload max memory
PAYLOAD_START:

.area 0x20, 0
RANDO_CONTEXT:
.word COOP_CONTEXT
.word COSMETIC_CONTEXT
.word extern_ctxt
.endarea

.include "coop_state.asm" ; This should always come first
.include "config.asm"
.include "init.asm"
.include "item_overrides.asm"
.include "cutscenes.asm"
.include "shop.asm"
.include "every_frame.asm"
.include "menu.asm"
.include "time_travel.asm"
.include "song_fix.asm"
.include "scarecrow.asm"
.include "empty_bomb_fix.asm"
.include "initial_save.asm"
.include "textbox.asm"
.include "fishing.asm"
.include "bgs_fix.asm"
.include "chus_in_logic.asm"
.include "rainbow_bridge.asm"
.include "lacs_condition.asm"
.include "gossip_hints.asm"
.include "potion_shop.asm"
.include "jabu_elevator.asm"
.include "dampe.asm"
.include "dpad.asm"
.include "chests.asm"
.include "bunny_hood.asm"
.include "magic_color.asm"
.include "debug.asm"
.include "extended_objects.asm"
.include "cow.asm"
.include "lake_hylia.asm"
.include "timers.asm"
.include "shooting_gallery.asm"
.include "damage.asm"
.include "bean_salesman.asm"
.include "grotto.asm"
.include "deku_mouth_condition.asm"
.include "audio.asm"
.include "king_zora.asm"
.include "agony.asm"
.importobj "../build/bundle.o"
.align 8
FONT_TEXTURE:
.incbin("../resources/font.bin")
DPAD_TEXTURE:
.incbin("../resources/dpad.bin")
TRIFORCE_ICON_TEXTURE:
.incbin("../resources/triforce_sprite.bin")

.align 0x10
PAYLOAD_END:
.endarea //payload max memory

AUDIO_THREAD_MEM_START:
.skip AUDIO_THREAD_MEM_SIZE
.close
