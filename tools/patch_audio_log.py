p = '/home/josha/src/PS2Recomp/ps2xRuntime/src/lib/ps2_audio.cpp'
s = open(p).read()
s = s.replace('''    PlayAudioStream(g_spuStream.stream);
    g_spuStream.live = true;''', '''    PlayAudioStream(g_spuStream.stream);
    g_spuStream.live = true;
    std::fprintf(stderr, "[audio] SPU stream live (48 kHz stereo)\\n");''', 1)
s = s.replace('#include <algorithm>\n#include <array>', '#include <algorithm>\n#include <array>\n#include <cstdio>', 1)
open(p, 'w').write(s)
print('ok')
