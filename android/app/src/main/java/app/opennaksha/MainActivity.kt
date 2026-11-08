package app.opennaksha

import android.os.Bundle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.appcompat.app.AppCompatActivity
import app.opennaksha.core.ui.theme.OpenNakshaTheme
import dagger.hilt.android.AndroidEntryPoint

/** AppCompatActivity so per-app language switching works on all supported Android versions. */
@AndroidEntryPoint
class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            OpenNakshaTheme {
                OpenNakshaRoot()
            }
        }
    }
}
