<!-- 登录/注册页面：支持顾客和商家角色切换 -->
<template>
  <div class="login-container">
    <el-card class="login-card" shadow="hover">
      <template #header>
        <div class="login-header">
          <el-icon :size="40" color="#409eff"><Food /></el-icon>
          <h2>美味餐厅</h2>
        </div>
      </template>

      <el-form :model="form" label-position="top" @submit.prevent="handleLogin">
        <el-form-item label="用户名">
          <el-input
            v-model="form.username"
            placeholder="请输入用户名"
            size="large"
          />
        </el-form-item>

        <el-form-item label="密码">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            size="large"
            show-password
          />
        </el-form-item>

        <el-form-item>
          <el-radio-group v-model="form.role">
            <el-radio label="customer">我是顾客</el-radio>
            <el-radio label="admin">我是商家</el-radio>
          </el-radio-group>
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            size="large"
            style="width: 100%"
            @click="handleLogin"
            :loading="loading"
          >
            登录
          </el-button>
        </el-form-item>

        <el-form-item v-if="form.role === 'customer'">
          <el-button
            size="large"
            style="width: 100%"
            @click="showRegister = true"
          >
            注册新账号
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 注册弹窗 -->
    <el-dialog v-model="showRegister" title="用户注册" width="400px">
      <el-form :model="registerForm" label-position="top">
        <el-form-item label="用户名">
          <el-input
            v-model="registerForm.username"
            placeholder="请输入用户名"
          />
        </el-form-item>
        <el-form-item label="密码">
          <el-input
            v-model="registerForm.password"
            type="password"
            placeholder="请输入密码"
            show-password
          />
        </el-form-item>
        <el-form-item label="确认密码">
          <el-input
            v-model="registerForm.confirmPassword"
            type="password"
            placeholder="请再次输入密码"
            show-password
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showRegister = false">取消</el-button>
        <el-button
          type="primary"
          @click="handleRegister"
          :loading="registerLoading"
          >注册</el-button
        >
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { login, register } from "@/features/auth/api/auth.api";
import { useAuthStore } from "@/features/auth/stores/auth.store";
import { useChatStore } from "@/features/chat/stores/chat.store";
import { useCartStore } from "@/features/cart/stores/cart.store";
import type { UserRole, ApiErrorDetail } from "@/shared/types";
import type { AxiosError } from "axios";

const router = useRouter();
const authStore = useAuthStore();
const chatStore = useChatStore();
const cartStore = useCartStore();

const form = reactive({
  username: "",
  password: "",
  role: "customer" as UserRole,
});

const loading = ref(false);
const showRegister = ref(false);
const registerLoading = ref(false);
const registerForm = reactive({
  username: "",
  password: "",
  confirmPassword: "",
});

async function handleLogin() {
  if (!form.username || !form.password) {
    ElMessage.warning("请输入用户名和密码");
    return;
  }
  loading.value = true;
  try {
    const res = await login({
      username: form.username,
      password: form.password,
    });
    const data = res.data;

    // 角色保护：商家账号必须选择商家入口登录
    if (form.role === "customer" && data.user.role === "admin") {
      form.role = "admin";
      await ElMessageBox.alert(
        "该账号为商家账号，请使用“我是商家”入口登录",
        "提示",
        {
          confirmButtonText: "确定",
          type: "warning",
        },
      );
      return;
    }

    authStore.setAuth({ user: data.user, token: data.token || "" });
    chatStore.reloadMessages();
    cartStore.reloadCart();

    if (form.role === "admin" && data.user.role !== "admin") {
      ElMessage.warning("该账号不是商家账号，已按顾客身份登录");
    } else {
      ElMessage.success(data.message);
    }

    if (data.user.role === "admin") {
      router.push("/admin");
    } else {
      router.push("/chat");
    }
  } catch (err) {
    const error = err as AxiosError<ApiErrorDetail>;
    ElMessage.error(error.response?.data?.detail || "登录失败");
  } finally {
    loading.value = false;
  }
}

async function handleRegister() {
  if (!registerForm.username || !registerForm.password) {
    ElMessage.warning("请填写完整信息");
    return;
  }
  if (registerForm.password !== registerForm.confirmPassword) {
    ElMessage.warning("两次输入的密码不一致");
    return;
  }
  registerLoading.value = true;
  try {
    await register({
      username: registerForm.username,
      password: registerForm.password,
    });
    ElMessage.success("注册成功，请登录");
    showRegister.value = false;
    form.username = registerForm.username;
    form.password = registerForm.password;
    registerForm.username = "";
    registerForm.password = "";
    registerForm.confirmPassword = "";
  } catch (err) {
    const error = err as AxiosError<ApiErrorDetail>;
    ElMessage.error(error.response?.data?.detail || "注册失败");
  } finally {
    registerLoading.value = false;
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: #f5f7fa;
}

.login-card {
  width: 420px;
}

.login-header {
  text-align: center;
}

.login-header h2 {
  margin: 10px 0 0;
  color: #303133;
}
</style>
