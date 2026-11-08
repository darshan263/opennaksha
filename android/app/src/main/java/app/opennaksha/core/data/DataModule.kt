package app.opennaksha.core.data

import android.content.Context
import androidx.room.Room
import app.opennaksha.BuildConfig
import app.opennaksha.core.data.db.AppDatabase
import app.opennaksha.core.data.db.CatalogDao
import app.opennaksha.core.data.db.UserDao
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.android.qualifiers.ApplicationContext
import dagger.hilt.components.SingletonComponent
import okhttp3.Cache
import okhttp3.OkHttpClient
import java.io.File
import java.util.concurrent.TimeUnit
import javax.inject.Singleton

@Module
@InstallIn(SingletonComponent::class)
object DataModule {
    @Provides
    @Singleton
    fun database(@ApplicationContext context: Context): AppDatabase =
        Room.databaseBuilder(context, AppDatabase::class.java, "opennaksha.db")
            .fallbackToDestructiveMigration(dropAllTables = true)
            .build()

    @Provides
    fun catalogDao(db: AppDatabase): CatalogDao = db.catalogDao()

    @Provides
    fun userDao(db: AppDatabase): UserDao = db.userDao()

    /** One client for catalog, overlays and PDFs. TLS verification is never disabled. */
    @Provides
    @Singleton
    fun okHttp(@ApplicationContext context: Context): OkHttpClient =
        OkHttpClient.Builder()
            .cache(Cache(File(context.cacheDir, "http"), 50L * 1024 * 1024))
            .connectTimeout(20, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .addInterceptor { chain ->
                chain.proceed(
                    chain.request().newBuilder()
                        .header("User-Agent", "OpenNaksha-Android/${BuildConfig.VERSION_NAME}")
                        .build(),
                )
            }
            .build()
}
