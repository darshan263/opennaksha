package app.opennaksha

import android.app.Application
import dagger.hilt.android.HiltAndroidApp
import org.maplibre.android.MapLibre

@HiltAndroidApp
class OpenNakshaApp : Application() {
    override fun onCreate() {
        super.onCreate()
        // MapLibre needs no API key. Initialise it once so map screens can be created later.
        MapLibre.getInstance(this)
    }
}
