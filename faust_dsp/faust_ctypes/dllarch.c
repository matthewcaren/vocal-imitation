#include "faust/gui/CInterface.h"

/* getting faustfloat option hard-written into code */
/* trick to expand macro inside string */
/* https://www.guyrutenberg.com/2008/12/20/expanding-macros-into-string-constants-in-c/ */

/* might already be present in metadata (note in example */
/* https://faustdoc.grame.fr/manual/architectures/#global-dsp-metadata) */

#define DLLARCH_STR_EXPAND(tok) #tok
#define DLLARCH_STR(tok) DLLARCH_STR_EXPAND(tok)

char* dllarch_faustfloat_name = DLLARCH_STR(FAUSTFLOAT);
size_t dllarch_faustfloat_size = sizeof(FAUSTFLOAT);

<<includeIntrinsic>>

<<includeclass>>
