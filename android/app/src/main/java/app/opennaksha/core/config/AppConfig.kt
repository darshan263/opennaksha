package app.opennaksha.core.config

import app.opennaksha.BuildConfig
import javax.inject.Inject
import javax.inject.Singleton

/** App-wide configuration. The only place the catalog base URL and basemap style are read. */
@Singleton
class AppConfig @Inject constructor() {
    /** Base URL of the published catalog (GitHub Pages), or null if not configured yet. */
    val catalogBaseUrl: String? = BuildConfig.CATALOG_BASE_URL.ifBlank { null }

    val mapStyleUrl: String = MapConfig.STYLE_URL
}

object MapConfig {
    /** Free, key-less OpenStreetMap-based basemap (OpenFreeMap). */
    const val STYLE_URL = "https://tiles.openfreemap.org/styles/liberty"
}

/** Builds published catalog URLs from a base URL, following the layout in PLAN.md §4. */
object CatalogUrls {
    fun index(base: String) = "${base.trimEnd('/')}/catalog/index.json"

    fun city(base: String, cityId: String) = "${base.trimEnd('/')}/catalog/cities/$cityId.json"

    fun changes(base: String) = "${base.trimEnd('/')}/catalog/changes.json"

    fun overlay(base: String, schemeId: String) = "${base.trimEnd('/')}/overlays/$schemeId.png"
}
