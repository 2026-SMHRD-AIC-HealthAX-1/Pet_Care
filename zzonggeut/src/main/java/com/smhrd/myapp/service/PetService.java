package com.smhrd.myapp.service;

import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.smhrd.myapp.entity.PetEntity;
import com.smhrd.myapp.repository.PetRepository;

import java.util.List;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class PetService {
    private final PetRepository petRepository;

    @Transactional
    public PetEntity savePet(String pName, char pGender, String pSpecies, Integer pAge, Integer pWeight,
                             String pSpec, char isMule, char isVaccin_1, char isVaccin_2, char isVaccin_3) {

		return petRepository.save(new PetEntity(pName, pGender, pSpecies, pAge, pWeight, pSpec, isMule, isVaccin_1, isVaccin_2, isVaccin_3));
    }

    public List getAllPets() {
        return petRepository.findAll();
    }
}