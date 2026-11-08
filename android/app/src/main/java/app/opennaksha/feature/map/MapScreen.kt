package app.opennaksha.feature.map

import android.Manifest
import android.annotation.SuppressLint
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.MyLocation
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.SavedStateHandle
import androidx.lifecycle.ViewModel
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewModelScope
import androidx.navigation.NavController
import app.opennaksha.R
import app.opennaksha.Routes
import app.opennaksha.core.config.MapConfig
import app.opennaksha.core.data.CatalogRepository
import app.opennaksha.core.data.OverlayRepository
import app.opennaksha.core.model.SchemeRecord
import app.opennaksha.core.ui.displayName
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import org.maplibre.android.camera.CameraPosition
import org.maplibre.android.camera.CameraUpdateFactory
import org.maplibre.android.geometry.LatLng
import org.maplibre.android.geometry.LatLngBounds
import org.maplibre.android.geometry.LatLngQuad
import org.maplibre.android.location.LocationComponentActivationOptions
import org.maplibre.android.location.modes.CameraMode
import org.maplibre.android.location.modes.RenderMode
import org.maplibre.android.maps.MapLibreMap
import org.maplibre.android.maps.MapView
import org.maplibre.android.maps.Style
import org.maplibre.android.style.layers.FillLayer
import org.maplibre.android.style.layers.LineLayer
import org.maplibre.android.style.layers.PropertyFactory
import org.maplibre.android.style.layers.RasterLayer
import org.maplibre.android.style.sources.GeoJsonSource
import org.maplibre.android.style.sources.ImageSource
import org.maplibre.geojson.Feature
import org.maplibre.geojson.FeatureCollection
import org.maplibre.geojson.Point
import org.maplibre.geojson.Polygon
import javax.inject.Inject

private const val SRC_OUTLINES = "scheme-outlines"
private const val LAYER_FILL = "scheme-fill"
private const val LAYER_LINE = "scheme-line"
private const val SRC_OVERLAY = "overlay-src"
private const val LAYER_OVERLAY = "overlay-layer"
private val GUJARAT = LatLng(22.3, 71.6)

/** Corners [[lon,lat] TL, TR, BR, BL] → MapLibre quad. */
fun SchemeRecord.quad(): LatLngQuad? {
    val c = overlay.corners?.takeIf { it.size == 4 && it.all { p -> p.size >= 2 } } ?: return null
    fun ll(i: Int) = LatLng(c[i][1], c[i][0])
    return LatLngQuad(ll(0), ll(1), ll(2), ll(3))
}

@HiltViewModel
class MapViewModel @Inject constructor(
    handle: SavedStateHandle,
    repo: CatalogRepository,
    private val overlays: OverlayRepository,
) : ViewModel() {
    val focusId: String? = handle.get<String>("focus")?.takeIf { it.isNotBlank() }
    val schemes: StateFlow<List<SchemeRecord>?> = repo.overlaySchemes.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), null)
    val selectedId = MutableStateFlow(focusId)
    val opacity = MutableStateFlow(0.7f)

    suspend fun overlayBitmap(record: SchemeRecord): Bitmap? = runCatching { overlays.load(record) }.getOrNull()
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MapScreen(nav: NavController, vm: MapViewModel = hiltViewModel()) {
    val context = LocalContext.current
    val schemes by vm.schemes.collectAsStateWithLifecycle()
    val selectedId by vm.selectedId.collectAsStateWithLifecycle()
    val opacity by vm.opacity.collectAsStateWithLifecycle()
    val selected = schemes?.firstOrNull { it.id == selectedId }

    val mapView = rememberMapViewWithLifecycle()
    var map by remember { mutableStateOf<MapLibreMap?>(null) }
    var style by remember { mutableStateOf<Style?>(null) }
    var overlayError by remember { mutableStateOf(false) }

    LaunchedEffect(mapView) {
        mapView.getMapAsync { m ->
            map = m
            m.cameraPosition = CameraPosition.Builder().target(GUJARAT).zoom(6.0).build()
            m.setStyle(Style.Builder().fromUri(MapConfig.STYLE_URL)) { s -> style = s }
            m.addOnMapClickListener { p ->
                val hit = m.queryRenderedFeatures(m.projection.toScreenLocation(p), LAYER_FILL).firstOrNull()
                val id = hit?.getStringProperty("id")
                if (id != null) vm.selectedId.value = id
                id != null
            }
        }
    }

    // Outlines for all georeferenced schemes.
    LaunchedEffect(style, schemes) {
        val s = style ?: return@LaunchedEffect
        val list = schemes ?: return@LaunchedEffect
        val features = list.mapNotNull { r ->
            val c = r.overlay.corners ?: return@mapNotNull null
            val ring = (c + listOf(c.first())).map { Point.fromLngLat(it[0], it[1]) }
            Feature.fromGeometry(Polygon.fromLngLats(listOf(ring))).apply { addStringProperty("id", r.id) }
        }
        val fc = FeatureCollection.fromFeatures(features)
        val src = s.getSourceAs<GeoJsonSource>(SRC_OUTLINES)
        if (src != null) {
            src.setGeoJson(fc)
        } else {
            s.addSource(GeoJsonSource(SRC_OUTLINES, fc))
            s.addLayer(FillLayer(LAYER_FILL, SRC_OUTLINES).withProperties(PropertyFactory.fillColor("#00695C"), PropertyFactory.fillOpacity(0.08f)))
            s.addLayer(LineLayer(LAYER_LINE, SRC_OUTLINES).withProperties(PropertyFactory.lineColor("#00695C"), PropertyFactory.lineWidth(2f)))
        }
        if (vm.focusId == null && list.isNotEmpty() && selectedId == null) {
            bounds(list)?.let { map?.easeCamera(CameraUpdateFactory.newLatLngBounds(it, 80)) }
        }
    }

    // The selected scheme's overlay image.
    LaunchedEffect(style, selected?.id, selected?.overlay?.pointsSha256) {
        val s = style ?: return@LaunchedEffect
        s.getLayer(LAYER_OVERLAY)?.let { s.removeLayer(it) }
        s.getSource(SRC_OVERLAY)?.let { s.removeSource(it) }
        overlayError = false
        val r = selected ?: return@LaunchedEffect
        val quad = r.quad() ?: return@LaunchedEffect
        bounds(listOf(r))?.let { map?.easeCamera(CameraUpdateFactory.newLatLngBounds(it, 60)) }
        val bmp = vm.overlayBitmap(r)
        if (bmp == null) {
            overlayError = true
            return@LaunchedEffect
        }
        if (style !== s) return@LaunchedEffect
        s.addSource(ImageSource(SRC_OVERLAY, quad, bmp))
        val layer = RasterLayer(LAYER_OVERLAY, SRC_OVERLAY).withProperties(PropertyFactory.rasterOpacity(vm.opacity.value))
        if (s.getLayer(LAYER_LINE) != null) s.addLayerBelow(layer, LAYER_LINE) else s.addLayer(layer)
    }

    LaunchedEffect(style, opacity) {
        style?.getLayer(LAYER_OVERLAY)?.setProperties(PropertyFactory.rasterOpacity(opacity))
    }

    val deniedMessage = stringResource(R.string.map_location_denied)
    val permissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->
        if (result.values.any { it }) {
            enableLocation(context, map, style)
        } else {
            Toast.makeText(context, deniedMessage, Toast.LENGTH_SHORT).show()
        }
    }

    Scaffold(
        topBar = { TopAppBar(title = { Text(stringResource(R.string.nav_map)) }) },
        floatingActionButton = {
            FloatingActionButton(onClick = {
                if (hasLocationPermission(context)) {
                    enableLocation(context, map, style)
                } else {
                    permissionLauncher.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION))
                }
            }) { Icon(Icons.Filled.MyLocation, contentDescription = stringResource(R.string.map_my_location)) }
        },
    ) { padding ->
        Box(Modifier.padding(padding).fillMaxSize()) {
            AndroidView(factory = { mapView }, modifier = Modifier.fillMaxSize())
            if (schemes?.isEmpty() == true) {
                Card(Modifier.align(Alignment.TopCenter).padding(12.dp)) {
                    Text(stringResource(R.string.map_no_overlays), modifier = Modifier.padding(12.dp))
                }
            }
            if (selected != null) {
                SelectedCard(
                    record = selected,
                    opacity = opacity,
                    overlayError = overlayError,
                    onOpacity = { vm.opacity.value = it },
                    onOpen = { nav.navigate(Routes.scheme(selected.id)) },
                    onClose = { vm.selectedId.value = null },
                    modifier = Modifier.align(Alignment.BottomCenter).padding(start = 12.dp, end = 80.dp, bottom = 12.dp),
                )
            }
        }
    }
}

@Composable
private fun SelectedCard(
    record: SchemeRecord,
    opacity: Float,
    overlayError: Boolean,
    onOpacity: (Float) -> Unit,
    onOpen: () -> Unit,
    onClose: () -> Unit,
    modifier: Modifier,
) {
    Card(modifier.fillMaxWidth(), elevation = CardDefaults.cardElevation(6.dp)) {
        Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(record.displayName(), style = MaterialTheme.typography.titleSmall, modifier = Modifier.weight(1f))
                IconButton(onClick = onClose) { Icon(Icons.Filled.Close, contentDescription = stringResource(R.string.map_close)) }
            }
            if (record.overlay.isOutdated) {
                Text(stringResource(R.string.map_outdated), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }
            if (overlayError) {
                Text(stringResource(R.string.map_overlay_error), color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }
            Text(
                listOfNotNull(stringResource(R.string.map_approximate), record.overlay.accuracyNote).joinToString(" · "),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(stringResource(R.string.map_opacity), style = MaterialTheme.typography.labelMedium)
            Slider(value = opacity, onValueChange = onOpacity, valueRange = 0f..1f)
            TextButton(onClick = onOpen) { Text(stringResource(R.string.map_open_scheme)) }
        }
    }
}

private fun bounds(list: List<SchemeRecord>): LatLngBounds? {
    val pts = list.flatMap { r -> r.overlay.corners.orEmpty().map { LatLng(it[1], it[0]) } }
    if (pts.size < 2) return null
    return LatLngBounds.Builder().includes(pts).build()
}

private fun hasLocationPermission(context: Context): Boolean =
    ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED ||
        ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_COARSE_LOCATION) == PackageManager.PERMISSION_GRANTED

@SuppressLint("MissingPermission") // checked by hasLocationPermission() first
private fun enableLocation(context: Context, map: MapLibreMap?, style: Style?) {
    if (map == null || style == null || !hasLocationPermission(context)) return
    val lc = map.locationComponent
    if (!lc.isLocationComponentActivated) {
        lc.activateLocationComponent(LocationComponentActivationOptions.builder(context, style).build())
    }
    lc.isLocationComponentEnabled = true
    lc.renderMode = RenderMode.COMPASS
    lc.cameraMode = CameraMode.TRACKING
    lc.zoomWhileTracking(15.0)
}

@Composable
private fun rememberMapViewWithLifecycle(): MapView {
    val context = LocalContext.current
    val mapView = remember { MapView(context).apply { onCreate(null) } }
    val lifecycle = LocalLifecycleOwner.current.lifecycle
    DisposableEffect(lifecycle, mapView) {
        var started = false
        var resumed = false
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_START -> { mapView.onStart(); started = true }
                Lifecycle.Event.ON_RESUME -> { mapView.onResume(); resumed = true }
                Lifecycle.Event.ON_PAUSE -> { mapView.onPause(); resumed = false }
                Lifecycle.Event.ON_STOP -> { mapView.onStop(); started = false }
                else -> {}
            }
        }
        lifecycle.addObserver(observer)
        onDispose {
            lifecycle.removeObserver(observer)
            if (resumed) mapView.onPause()
            if (started) mapView.onStop()
            mapView.onDestroy()
        }
    }
    return mapView
}
