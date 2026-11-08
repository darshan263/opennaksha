package app.opennaksha.core.data

import app.opennaksha.TestData
import kotlinx.coroutines.test.runTest
import okhttp3.OkHttpClient
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class FakeStore(var meta: StoredMeta = StoredMeta(null, null, null)) : CatalogStore {
    var snapshot: CatalogSnapshot? = null
    var replaceCount = 0
    var checkedAt: Long? = null

    override suspend fun storedMeta() = meta
    override suspend fun replace(snapshot: CatalogSnapshot, etag: String?, lastModified: String?, source: String) {
        this.snapshot = snapshot
        replaceCount++
        meta = StoredMeta(snapshot.index.generatedAt, etag, lastModified)
    }
    override suspend fun saveValidators(etag: String?, lastModified: String?) {
        meta = meta.copy(etag = etag, lastModified = lastModified)
    }
    override suspend fun markChecked(nowMs: Long) {
        checkedAt = nowMs
    }
}

class CatalogUpdaterTest {
    private lateinit var server: MockWebServer
    private val client = OkHttpClient()
    private val routes = mutableMapOf<String, () -> MockResponse>()
    private val requests = mutableListOf<RecordedRequest>()

    @Before
    fun setUp() {
        server = MockWebServer()
        server.dispatcher = object : Dispatcher() {
            override fun dispatch(request: RecordedRequest): MockResponse {
                requests += request
                return routes[request.path]?.invoke() ?: MockResponse().setResponseCode(404)
            }
        }
        server.start()
        routes["/repo/catalog/index.json"] = { MockResponse().setBody(TestData.index).setHeader("ETag", "\"v1\"") }
        routes["/repo/catalog/cities/testcity.json"] = { MockResponse().setBody(TestData.city) }
        routes["/repo/catalog/changes.json"] = { MockResponse().setBody(TestData.changes) }
    }

    @After
    fun tearDown() = server.shutdown()

    private fun updater(store: CatalogStore) =
        CatalogUpdater(client, server.url("/repo").toString().trimEnd('/'), store) { 42L }

    @Test
    fun notConfiguredWithoutBaseUrl() = runTest {
        assertEquals(UpdateResult.NotConfigured, CatalogUpdater(client, null, FakeStore()).update())
    }

    @Test
    fun newDataReplacesStoreAtomically() = runTest {
        val store = FakeStore(StoredMeta("1970-01-01T00:00:00Z", null, null))
        val result = updater(store).update()
        assertEquals(UpdateResult.Updated("2026-11-15T02:00:00Z"), result)
        assertEquals(1, store.replaceCount)
        assertEquals(2, store.snapshot!!.cities.single().schemes.size)
        assertEquals(2, store.snapshot!!.changes!!.runs.size)
        assertEquals("\"v1\"", store.meta.etag)
        assertEquals(42L, store.checkedAt)
    }

    @Test
    fun sendsValidatorsAnd304KeepsData() = runTest {
        routes["/repo/catalog/index.json"] = { MockResponse().setResponseCode(304) }
        val store = FakeStore(StoredMeta("2026-11-15T02:00:00Z", "\"v1\"", "Sat, 14 Nov 2026 10:00:00 GMT"))
        assertEquals(UpdateResult.NotModified, updater(store).update())
        assertEquals(0, store.replaceCount)
        val req = requests.first()
        assertEquals("\"v1\"", req.getHeader("If-None-Match"))
        assertEquals("Sat, 14 Nov 2026 10:00:00 GMT", req.getHeader("If-Modified-Since"))
        assertEquals(42L, store.checkedAt)
    }

    @Test
    fun sameGeneratedAtIsUpToDate() = runTest {
        val store = FakeStore(StoredMeta("2026-11-15T02:00:00Z", null, null))
        assertEquals(UpdateResult.UpToDate, updater(store).update())
        assertEquals(0, store.replaceCount)
        assertEquals(1, requests.size) // city files not downloaded
        assertEquals("\"v1\"", store.meta.etag)
    }

    @Test
    fun invalidJsonKeepsData() = runTest {
        routes["/repo/catalog/index.json"] = { MockResponse().setBody("{not json") }
        val store = FakeStore()
        assertTrue(updater(store).update() is UpdateResult.Failed)
        assertEquals(0, store.replaceCount)
    }

    @Test
    fun unsupportedSchemaVersionKeepsData() = runTest {
        routes["/repo/catalog/index.json"] = {
            MockResponse().setBody(TestData.index.replace("\"schema_version\":1", "\"schema_version\":99"))
        }
        val store = FakeStore()
        assertTrue(updater(store).update() is UpdateResult.Failed)
        assertEquals(0, store.replaceCount)
    }

    @Test
    fun brokenCityFileKeepsAllData() = runTest {
        routes["/repo/catalog/cities/testcity.json"] = { MockResponse().setResponseCode(500) }
        val store = FakeStore()
        assertTrue(updater(store).update() is UpdateResult.Failed)
        assertEquals(0, store.replaceCount)
        assertNull(store.meta.generatedAt)
    }

    @Test
    fun missingChangesFileStillUpdates() = runTest {
        routes.remove("/repo/catalog/changes.json")
        val store = FakeStore()
        assertTrue(updater(store).update() is UpdateResult.Updated)
        assertNull(store.snapshot!!.changes)
    }

    @Test
    fun networkErrorKeepsData() = runTest {
        val store = FakeStore()
        server.shutdown()
        assertTrue(updater(store).update() is UpdateResult.Failed)
        assertEquals(0, store.replaceCount)
    }

    @Test
    fun bundledLoaderLoadsAndDecides() {
        val files = mapOf(
            "catalog/index.json" to TestData.index,
            "catalog/cities/testcity.json" to TestData.city,
        )
        val loader = BundledCatalogLoader { files[it] }
        val snap = loader.load()!!
        assertEquals("testcity", snap.cities.single().cityId)
        assertNull(snap.changes)
        assertTrue(loader.shouldLoad(snap.index, StoredMeta(null, null, null)))
        assertTrue(loader.shouldLoad(snap.index, StoredMeta("1970-01-01T00:00:00Z", null, null)))
        assertTrue(!loader.shouldLoad(snap.index, StoredMeta("2026-11-15T02:00:00Z", null, null)))
        assertNull(BundledCatalogLoader { null }.load())
    }
}
