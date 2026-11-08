# Project-specific R8 rules. Library rules (Compose, Hilt, Room, MapLibre, OkHttp) ship with their AARs.

# kotlinx.serialization: keep generated serializers for our catalog models.
-keepattributes *Annotation*, InnerClasses
-dontnote kotlinx.serialization.**
-keepclassmembers @kotlinx.serialization.Serializable class app.opennaksha.** {
    *** Companion;
    kotlinx.serialization.KSerializer serializer(...);
}
-keep,includedescriptorclasses class app.opennaksha.**$$serializer { *; }
