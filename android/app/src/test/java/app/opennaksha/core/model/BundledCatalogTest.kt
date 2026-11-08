package app.opennaksha.core.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File

/**
 * Parses the catalog actually bundled in the APK (src/main/assets/catalog, real pipeline output
 * copied by scripts/sync_assets.*), so a pipeline/app schema mismatch fails the build.
 */
class BundledCatalogTest {
    private val dir = File("src/main/assets/catalog")

    @Test
    fun bundledCatalogParses() {
        val index = CatalogJson.decodeFromString(
            CatalogIndex.serializer(),
            File(dir, "index.json").readText(),
        )
        assertTrue(index.schemaVersion <= SUPPORTED_SCHEMA_VERSION)
        val ids = mutableSetOf<String>()
        for (city in index.cities) {
            val file = CatalogJson.decodeFromString(
                CityFile.serializer(),
                File(dir, "cities/${city.id}.json").readText(),
            )
            assertEquals(city.id, file.cityId)
            assertTrue("no schemes in ${city.id}", file.schemes.isNotEmpty())
            for (s in file.schemes) {
                assertTrue("duplicate id ${s.id}", ids.add(s.id))
                assertTrue(s.sourcePageUrl.startsWith("http"))
                s.files.forEach { assertTrue(it.url.startsWith("http")) }
            }
        }
        val changes = File(dir, "changes.json")
        if (changes.exists()) {
            CatalogJson.decodeFromString(ChangesFile.serializer(), changes.readText())
        }
    }
}
