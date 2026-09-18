package com.smhrd.myapp.controller;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.*;

import com.smhrd.myapp.entity.UserEntity;
import com.smhrd.myapp.service.UserService;

import jakarta.servlet.http.HttpSession;
import org.springframework.ui.Model;

@Controller
@RequiredArgsConstructor
@RequestMapping("/api/users")
public class UserController {
    private final UserService userService;

    @PostMapping("/join")
    @ResponseBody
    public String join(
            @RequestParam String id,
            @RequestParam String pw,
            @RequestParam String name,
            @RequestParam String phone
    ) {
        return userService.join(id, pw, name, phone);
    }
    
    @PostMapping("/login") // 
    public String login(
            @RequestParam("id") String id,
            @RequestParam("pw") String pw,
            HttpSession session,
            org.springframework.web.servlet.mvc.support.RedirectAttributes rttr
    ) {
        UserEntity user = userService.login(id, pw);
        
        if (user == null) {
            // 로그인 실패 시: 에러 메시지를 일회성으로 담아서 로그인 페이지로 리다이렉트!
            rttr.addFlashAttribute("errorMessage", "아이디 또는 비밀번호를 다시 확인해주세요.");
            return "redirect:/login"; // 로그인 페이지 주소
        }
        
        // 로그인 성공 시 세션에 저장
        session.setAttribute("loginUser", user);
        return "redirect:/main";
    }
    
 // 회원 정보 수정 처리
    @PostMapping("/update")
    public String update(
            @RequestParam("id") String id,
            @RequestParam("name") String name,
            @RequestParam("phone") String phone,
            HttpSession session,
            jakarta.servlet.http.HttpServletRequest request
    ) {
    	// 🔍 여기에 로그 찍기!
        System.out.println(">>> update 메서드 실행됨! 받은 이름: " + name);
    	
        // 1. DB 업데이트 실행
        userService.updateUser(id, name, phone);
        
       // 2. DB에서 최신 정보 다시 조회
        UserEntity updatedUser = userService.findId(id); // (사용 중이신 조회 메서드명으로 확인!)
        
        // 3. 기존 세션 날리고 새로운 세션에 최신 유저 정보 담기
        session.invalidate(); // 기존 세션 폐기
        HttpSession newSession = request.getSession(true); // 새 세션 생성
        newSession.setAttribute("loginUser", updatedUser); // 새 세션에 쏙!
        
        // 4. 마이페이지로 리다이렉트
        return "redirect:/mypage";
    }
    
 // 비밀번호 변경 페이지로 이동
    @GetMapping("/changepw")
    public String changePasswordPage(HttpSession session) {
        // 로그인이 안 되어 있다면 로그인 페이지로 튕겨내기
        if (session.getAttribute("loginUser") == null) {
            return "redirect:/login";
        }
        return "html/changePassword"; // templates/html/changePassword.html (또는 본인의 경로)
    }
    
 // 실제 비밀번호 변경 실행
    @PostMapping("/password/update")
    public String updatePassword(
            @RequestParam("currentPassword") String currentPassword,
            @RequestParam("newPassword") String newPassword,
            @RequestParam("confirmPassword") String confirmPassword,
            HttpSession session,
            org.springframework.web.servlet.mvc.support.RedirectAttributes rttr
    ) {
        // 로그인 유저 세션 확인
        UserEntity loginUser = (UserEntity) session.getAttribute("loginUser");
        if (loginUser == null) {
            return "redirect:/login";
        }

        // 1. 새 비밀번호와 확인란 일치 여부 재확인
        if (!newPassword.equals(confirmPassword)) {
            rttr.addFlashAttribute("errorMessage", "새 비밀번호가 일치하지 않습니다.");
            return "redirect:/changepw";
        }

        // 2. 서비스단에서 현재 비밀번호 검증 및 업데이트 수행
        boolean isUpdated = userService.updatePassword(loginUser.getId(), currentPassword, newPassword);

        if (!isUpdated) {
            // 현재 비밀번호가 틀렸을 때 에러 페이지 대신 알럿 메시지 전달!
            rttr.addFlashAttribute("errorMessage", "현재 비밀번호가 일치하지 않습니다. 다시 확인해 주세요.");
            return "redirect:/changepw";
        }

        // 3. 성공 시 성공 메시지 전달 후 마이페이지로 이동
        rttr.addFlashAttribute("successMessage", "비밀번호가 성공적으로 변경되었습니다.");
        
        // 세션 정보의 비밀번호도 최신화 (선택사항)
        loginUser.setPw(newPassword);
        session.setAttribute("loginUser", loginUser);

        return "redirect:/login";
    }
    
 // 1. 회원탈퇴 페이지로 이동
    @GetMapping("/withdraw")
    public String withdrawPage(HttpSession session) {
        if (session.getAttribute("loginUser") == null) {
            return "redirect:/login";
        }
        return "html/withdraw"; // templates/html/withdraw.html 경로에 맞게 수정해주세요!
    }

    // 2. 실제 회원탈퇴 실행
    @PostMapping("/withdraw/process")
    public String withdraw(
            @RequestParam("password") String password,
            HttpSession session,
            org.springframework.web.servlet.mvc.support.RedirectAttributes rttr
    ) {
        UserEntity loginUser = (UserEntity) session.getAttribute("loginUser");
        if (loginUser == null) {
            return "redirect:/login";
        }

        // 서비스단에서 비밀번호 검증 및 삭제 처리
        boolean isDeleted = userService.withdrawUser(loginUser.getId(), password);

        if (!isDeleted) {
            // 비밀번호가 틀렸을 때 에러 메시지 전달 후 탈퇴 페이지로 복귀
            rttr.addFlashAttribute("errorMessage", "비밀번호가 일치하지 않습니다. 다시 확인해 주세요.");
            return "redirect:/withdraw";
        }

        // 탈퇴 성공 시: 세션 완전히 파기 (로그아웃 처리)
        session.invalidate();

        rttr.addFlashAttribute("successMessage", "그동안 쫑긋을 이용해 주셔서 감사합니다. 회원탈퇴가 완료되었습니다.");
        return "redirect:/main"; // 탈퇴 후 메인페이지로 이동
    }
    
 // 1. 아이디 찾기 페이지로 이동 (GET)
    @GetMapping("/find-id")
    public String findIdPage(org.springframework.ui.Model model) {
        // 만약 리다이렉트를 통해 넘어온 foundId가 없다면 null로 초기화
        if (!model.containsAttribute("foundId")) {
            model.addAttribute("foundId", null);
        }
        return "html/findId"; 
    }

    // 2. 아이디 찾기 처리 (POST)
    @PostMapping("/find-id/process")
    public String findIdProcess(
            @RequestParam("name") String name,
            @RequestParam("phone") String phone,
            org.springframework.web.servlet.mvc.support.RedirectAttributes rttr
    ) {
        System.out.println(">>> 아이디 찾기 요청 진입! 이름: " + name + ", 전화번호: " + phone);

        String foundId = userService.findUserByNamerAndPhone(name, phone);
        System.out.println(">>> DB에서 찾은 아이디 결과: " + foundId);

        if (foundId == null) {
            rttr.addFlashAttribute("errorMessage", "일치하는 회원 정보를 찾을 수 없습니다.");
            return "redirect:/api/users/find-id";
        }

        // 💡 찾은 아이디를 RedirectAttributes(FlashAttribute)에 담아서 페이지를 다시 부릅니다.
        rttr.addFlashAttribute("foundId", foundId);
        return "redirect:/api/users/find-id";
    }
    
 // 1. 비밀번호 찾기(재설정) 페이지로 이동 (GET)
    @GetMapping("/find-pw")
    public String findPasswordPage() {
        return "html/findPw"; // templates/html/findPassword.html 경로
    }

    // 2. 비밀번호 재설정 처리 (POST)
 // 비밀번호 재설정 처리
    @PostMapping("/find-pw/process")
    public String findPasswordProcess(
            @RequestParam("id") String id,
            @RequestParam("phone") String phone,
            @RequestParam("newPassword") String newPassword,
            org.springframework.web.servlet.mvc.support.RedirectAttributes rttr
    ) {
        String result = userService.resetPassword(id, phone, newPassword);

        if (result.equals("NOT_FOUND")) {
            rttr.addFlashAttribute("errorMessage", "일치하는 회원 정보가 없습니다. 아이디와 전화번호를 확인해주세요.");
            return "redirect:/api/users/find-pw";
        }
        
        // 💡 기존 비밀번호와 같을 때의 경고 메시지!
        if (result.equals("SAME_PASSWORD")) {
            rttr.addFlashAttribute("errorMessage", "새 비밀번호는 기존 비밀번호와 달라야 합니다. 다른 비밀번호를 입력해주세요.");
            return "redirect:/api/users/find-pw";
        }

        // 성공 시
        rttr.addFlashAttribute("errorMessage", "비밀번호가 성공적으로 변경되었습니다. 새 비밀번호로 로그인해주세요.");
        return "redirect:/signup"; 
    }
 
}