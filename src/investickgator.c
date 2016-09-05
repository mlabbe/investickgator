/*
 * InveSTICKgator Copyright (C) 2016 Frogtoss Games, Inc
 * 
 */

#include "ivconfig.h"
#include "ftg_core.h"

#include <stdlib.h>
#include <string.h>
#include <SDL.h>
#include <stdio.h>
#include <stdlib.h>
#include <GL/glew.h>


#include "ui.h"

#define WINDOW_WIDTH 1024
#define WINDOW_HEIGHT 768

#define MAX_VERTEX_MEMORY 512 * 1024
#define MAX_ELEMENT_MEMORY 128 * 1024

#define MAX_JOYSTICKS 16

struct ik_ctx {
    SDL_Window *win;
    SDL_GLContext gl;
    struct nk_context *nk;
    
    int width;
    int height;
    struct nk_color bg_color;
};

struct joysticks {
    SDL_Joystick *ptr[MAX_JOYSTICKS];
    bool has_haptics[MAX_JOYSTICKS];
};

static void init_joysticks(struct joysticks *joys)
{
    ftg_bzero(joys, sizeof(struct joysticks));    
}


bool g_enable_xinput = true;

static void fatal(const char *msg)
{
    fprintf(stderr, "InveSTICKgator error: %s\n", msg);
    SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_ERROR, "InveSTICKgator error", msg, NULL);
    exit(1);
}
#if 0
static const char *get_joystick_name(int device_index)
{
    const char *name = SDL_JoystickNameForIndex(device_index);
    if (name)
        return name;
    else
        printf("get_joystick_name() error: %s\n", SDL_GetError());
    return "(unnamed controller)";
}
#endif
static const char *get_joystick_name(SDL_Joystick *joy)
{
    const char *name = SDL_JoystickName(joy);
    if (name)
        return name;
    else
    {
        printf("get_joystick_name() error: %s\n", SDL_GetError());
        FTG_BREAK();
    }

    return "(unnamed controller)";
}

static void restart_joystick_subsystems(bool first_time, bool enable_xinput)
{
    printf("Starting joystick subsystem with xinput enabled: %d\n", enable_xinput);
    bool result;
    if (enable_xinput)
        result = SDL_SetHint(SDL_HINT_XINPUT_ENABLED, "1");
    else
        result = SDL_SetHint(SDL_HINT_XINPUT_ENABLED, "0");
    FTG_ASSERT(result);

    if (!first_time)
        SDL_QuitSubSystem(SDL_INIT_JOYSTICK|SDL_INIT_HAPTIC);
    
    if (SDL_InitSubSystem(SDL_INIT_JOYSTICK|SDL_INIT_HAPTIC) != 0)
        fatal(ftg_va("unable to (re)start joystick subsystems: %s", SDL_GetError()));
}

static void init(struct ik_ctx *ctx, struct joysticks *joys)
{
#ifdef DEBUG
    ftg_alloc_console();
#endif
    init_joysticks(joys);
    
    // SDL
    SDL_SetHint(SDL_HINT_VIDEO_HIGHDPI_DISABLED, "0");

    if (SDL_Init(SDL_INIT_VIDEO|SDL_INIT_TIMER|SDL_INIT_EVENTS) != 0)
        fatal(ftg_va("unable to init SDL: %s", SDL_GetError()));

    restart_joystick_subsystems(true, g_enable_xinput);
    
    SDL_GL_SetAttribute (SDL_GL_CONTEXT_FLAGS, SDL_GL_CONTEXT_FORWARD_COMPATIBLE_FLAG);
    SDL_GL_SetAttribute (SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1);
    ctx->win = SDL_CreateWindow("InveSTICKgator",
                                SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED,
                                ctx->width, ctx->height,
                                SDL_WINDOW_OPENGL|SDL_WINDOW_SHOWN|SDL_WINDOW_ALLOW_HIGHDPI);
    ctx->gl = SDL_GL_CreateContext(ctx->win);
    SDL_GetWindowSize(ctx->win, &ctx->width, &ctx->height);

    // OpenGL
    glViewport(0, 0, ctx->width, ctx->height);
    glewExperimental = 1;
    GLenum err = glewInit();
    if (glewInit() != GLEW_OK)
        fatal(ftg_va("Failed to init glew: %s", glewGetErrorString(err)));

    // nk
    ctx->nk = nk_sdl_init(ctx->win);
    struct nk_font_atlas *atlas;
    nk_sdl_font_stash_begin(&atlas);
    nk_sdl_font_stash_end();
    ctx->bg_color = nk_rgb(24,48,62);
}

static struct nk_color color_from_guid(const char *guid)
{
    // 'hash' a color together from the guid
    struct nk_color color = {0};
    size_t len = strlen(guid);
    int hue = 0;
    for (int i = 0; i < len; i++)
    {
        hue += (int)(guid[i]);
        hue %= 360;
    }

    float r, g, b;
    ftg_getrgb((float)hue, 0.8f, 0.8f, &r, &g, &b);
    color.r = (nk_byte)(r * 255.0f);
    color.g = (nk_byte)(g * 255.0f);
    color.b = (nk_byte)(b * 255.0f);
    color.a = 0xFF;
    
    return color;
}

static const char *get_power_level_for_joystick(SDL_Joystick *js)
{
    switch (SDL_JoystickCurrentPowerLevel(js)) {
    case SDL_JOYSTICK_POWER_UNKNOWN:
        return "unknown";
    case SDL_JOYSTICK_POWER_EMPTY:
        return "empty";
    case SDL_JOYSTICK_POWER_LOW:
        return "low";
    case SDL_JOYSTICK_POWER_MEDIUM:
        return "medium";
    case SDL_JOYSTICK_POWER_FULL:
        return "full";
    case SDL_JOYSTICK_POWER_WIRED:
        return "wired";
    case SDL_JOYSTICK_POWER_MAX:
        return "max";
    default:
        return "error";
    }
}

static void joystick_panel(struct nk_context *nk, SDL_Joystick *js, int device_index, SDL_JoystickID instance_id,
                           bool has_haptics)
{
    const float W = 500.0f;
    struct nk_panel layout;

    float offset = device_index * 50.0f;

    const char *title = ftg_va("%s | instance id %d",
                               get_joystick_name(js),
                               instance_id);
    if (nk_begin(nk, &layout, title, nk_rect(10.0f + offset, 5 + offset, W, 325),
                 NK_WINDOW_BORDER|NK_WINDOW_MOVABLE|NK_WINDOW_SCALABLE|
                 NK_WINDOW_MINIMIZABLE|NK_WINDOW_TITLE))
    {
        // metadata
        {
            char guid_str[FTG_STRLEN];
            SDL_JoystickGUID guid = SDL_JoystickGetGUID(js);
            SDL_JoystickGetGUIDString(guid, guid_str, FTG_STRLEN);

            nk_layout_row_static(nk, 30, 30, 1);
            nk_button_color(nk, color_from_guid(guid_str));
            
            nk_layout_row_dynamic(nk, 30, 2);
            nk_label(nk, ftg_va("guid: %s", guid_str), NK_TEXT_LEFT);
            nk_label(nk, ftg_va("power level: %s", get_power_level_for_joystick(js)), NK_TEXT_RIGHT);
        }

        // buttons
        int num_buttons = SDL_JoystickNumButtons(js);
        if (num_buttons)
        {
            nk_layout_row_dynamic(nk, 20, 1);
            nk_label(nk, "buttons", NK_TEXT_CENTERED);
            nk_layout_row_dynamic(nk, 20, num_buttons);
            for (int i = 0; i < num_buttons; i++)
            {
                int on = SDL_JoystickGetButton(js, i);
                nk_check_label(nk, ftg_va("%d", i), on);
            }
        }

        // axes
        int num_axes = SDL_JoystickNumAxes(js);
        if (num_axes)
        {
            nk_layout_row_dynamic(nk, 20, 1);
            nk_label(nk, "axes", NK_TEXT_CENTERED);
            nk_layout_row_dynamic(nk, 20, num_axes*2);
            for (int i = 0; i < num_axes; i++)
            {
                int axis = SDL_JoystickGetAxis(js, i);
                size_t saxis = axis + 32768;
                nk_progress(nk, &saxis, 65535, NK_FIXED);
                nk_label(nk, ftg_va("%d", i), NK_TEXT_LEFT);
            }
        }

        // hats
        int num_hats = SDL_JoystickNumHats(js);
        if (num_hats)
        {
            enum nk_symbol_type SYM_OFF = NK_SYMBOL_RECT_FILLED;
            
            nk_layout_row_dynamic(nk, 20, 1);
            nk_label(nk, "hats", NK_TEXT_CENTERED);
            for (int i = 0; i < num_hats; i++)
            {
                uint8_t hat_pos = SDL_JoystickGetHat(js, i);
                nk_layout_row_static(nk, 30, 30, 5);
                nk_label(nk, ftg_va("#%d", i), NK_TEXT_RIGHT);
                nk_button_symbol(nk, (hat_pos&SDL_HAT_UP)? NK_SYMBOL_TRIANGLE_UP:SYM_OFF);
                nk_button_symbol(nk, (hat_pos&SDL_HAT_DOWN)? NK_SYMBOL_TRIANGLE_DOWN:SYM_OFF);
                nk_button_symbol(nk, (hat_pos&SDL_HAT_LEFT)? NK_SYMBOL_TRIANGLE_LEFT:SYM_OFF);
                nk_button_symbol(nk, (hat_pos&SDL_HAT_RIGHT)? NK_SYMBOL_TRIANGLE_RIGHT:SYM_OFF);
            }
        }
        
        // balls
        // todo: get a joystick with balls and write this code.

        // haptic support        
        {
            nk_layout_row_dynamic(nk, 20, 1);            
            if (has_haptics)
            {
                if (nk_button_label(nk, "haptic feedback"))
                {                                
                    SDL_Haptic *haptic = SDL_HapticOpenFromJoystick(js);
                    SDL_HapticRumbleInit(haptic);
                    SDL_HapticRumblePlay(haptic, 0.9f, 1000);
                    SDL_Delay(1000);
                    SDL_HapticClose(haptic);
                }
            }
            else
            {
                nk_label(nk, "haptics: unavailable", NK_TEXT_CENTERED);
            }
        }

    }
    nk_end(nk);
}

static void sim(bool *quit, struct nk_context *nk, struct joysticks *joys, int window_width, int window_height)
{
    // input
    SDL_Event event;
    nk_input_begin(nk);
    while (SDL_PollEvent(&event)) {
        switch(event.type){
        case SDL_QUIT:
            *quit = true;
            break;

        case SDL_JOYDEVICEADDED:
            {                
                int device_id = event.jdevice.which;
                
                SDL_Joystick *joystick = SDL_JoystickOpen(device_id);
                if (!joystick)
                {
                    printf("Joystick open failed: %s\n", SDL_GetError());
                    break;
                }
                const char *name = get_joystick_name(joystick);
                printf("\nadded device id %d with name %s\n",
                    event.jdevice.which, name);

                // test for haptics
                SDL_Haptic *haptic = SDL_HapticOpenFromJoystick(joystick);
                bool has_haptics = (haptic != NULL);
                if (haptic)
                    SDL_HapticClose(haptic);

                // find a spot for it
                bool found = false;
                for (int i = 0; i < MAX_JOYSTICKS; ++i)
                {
                    if (joys->ptr[i] == NULL) {
                        joys->ptr[i] = joystick;
                        joys->has_haptics[i] = has_haptics;
                        found = true;
                        break;
                    }
                }
                FTG_ASSERT(found);
                
                SDL_JoystickID instance_id = SDL_JoystickInstanceID(joystick);
                printf("Joystick instance id: %d\n", instance_id);
            }
            break;

        case SDL_JOYDEVICEREMOVED:
            {
                // note that 'which' here is the instance id, but it's the device index in added                
                int32_t instance_id = event.jdevice.which;
                SDL_Joystick *js = SDL_JoystickFromInstanceID(instance_id);
                FTG_ASSERT(js);

                // Remove it from the array
                bool found = false;
                for (int i = 0; i < MAX_JOYSTICKS; i++)
                {
                    if (js == joys->ptr[i]) {
                        joys->ptr[i] = NULL;
                        joys->has_haptics[i] = false;
                        found = true;
                        break;
                    }
                }
                FTG_ASSERT(found);
                SDL_JoystickClose(js);
                printf("\nremoved instance id %d\n", instance_id);                    
            }
            
            break;
        }
        
        nk_sdl_handle_event(&event);
    }
    nk_input_end(nk);

    // imgui
    struct nk_panel layout;
    if (nk_begin(nk, &layout, "Joystick Status", nk_rect((float)window_width-210, 5, 200, 200),
            NK_WINDOW_BORDER|
            NK_WINDOW_MINIMIZABLE|NK_WINDOW_TITLE))
    {        
        nk_layout_row_dynamic(nk, 30, 1);
        nk_label(nk, ftg_va("%d joystick(s) connected", SDL_NumJoysticks()), NK_TEXT_CENTERED);
        nk_layout_row_dynamic(nk, 30, 1);
#ifdef _WIN32
        if (g_enable_xinput)
        {
            char label[] = "disable xinput";
            if (nk_button_label(nk, label))
            {
                g_enable_xinput = !g_enable_xinput;
                restart_joystick_subsystems(false, g_enable_xinput);
                init_joysticks(joys);
            }            
        }
#endif        
    }
    nk_end(nk);

    for (int i = 0; i < MAX_JOYSTICKS; i++)
    {
        if (!joys->ptr[i]) continue;
        int32_t instance_id = SDL_JoystickInstanceID(joys->ptr[i]);

        joystick_panel(nk, joys->ptr[i], i, instance_id, joys->has_haptics[i]);
    }
}

static void render(SDL_Window *win, struct nk_color *bg_color)
{
    float bg[4];
    nk_color_fv(bg, *bg_color);
    glClear(GL_COLOR_BUFFER_BIT);
    glClearColor(bg[0], bg[1], bg[2], bg[3]);
    nk_sdl_render(NK_ANTI_ALIASING_ON, MAX_VERTEX_MEMORY, MAX_ELEMENT_MEMORY);
    SDL_GL_SwapWindow(win);
}

static void shutdown(struct ik_ctx *ctx)
{
    nk_sdl_shutdown();
    SDL_GL_DeleteContext(ctx->gl);
    SDL_DestroyWindow(ctx->win);
    SDL_Quit();
#ifdef DEBUG
    ftg_free_console();
#endif
}

int main(int argc, char *argv[]) {
    struct ik_ctx ctx = {0};
    ctx.width = WINDOW_WIDTH;
    ctx.height = WINDOW_HEIGHT;
    struct joysticks joys;
    
    init(&ctx, &joys);

    bool quit = false;
    while (!quit) {
        sim(&quit, ctx.nk, &joys, ctx.width, ctx.height);
        render(ctx.win, &ctx.bg_color);
    }

    shutdown(&ctx);
    
    return 0;
}

